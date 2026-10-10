from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

GROUP_DEPT_HEAD = 'manpower_requisition.group_dept_head'
GROUP_HR = 'manpower_requisition.group_hr'
GROUP_CEO = 'manpower_requisition.group_ceo'


class ManpowerRequirement(models.Model):
    _name = 'manpower.requirement'
    _description = 'Manpower Requirement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', default='New', readonly=True, copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('hr_review', 'HR Review'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True, copy=False, required=True)

    # Client call details (we act as a mediator for the client)
    client_id = fields.Many2one('res.partner', string='Client', tracking=True)
    client_contact = fields.Char(string='Contact Person')
    call_date = fields.Date(string='Call Date', default=fields.Date.context_today)
    call_notes = fields.Text(string='Call Notes')

    # Requirement details
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    job_title = fields.Char(string='Position', required=True, tracking=True)
    vacancies = fields.Integer(string='Number of Vacancies', default=1, tracking=True)
    qualification = fields.Char(string='Qualification')
    location = fields.Char(string='Location')
    reason = fields.Selection([
        ('new_position', 'New Position'),
        ('replacement', 'Replacement'),
        ('expansion', 'Expansion'),
        ('project', 'Project Requirement'),
        ('other', 'Other'),
    ], string='Reason for Requirement', default='new_position')
    reason_note = fields.Text(string='Reason Details')
    joining_requirement = fields.Selection([
        ('immediate', 'Immediate'),
        ('15', 'Within 15 days'),
        ('30', 'Within 30 days'),
        ('60', 'Within 60 days'),
        ('90', 'Within 90 days'),
        ('other', 'Other'),
    ], string='Joining Requirement')
    joining_date = fields.Date(string='Expected Joining Date')

    # Filled by HR
    experience_min = fields.Float(string='Min Experience (yrs)', tracking=True)
    experience_max = fields.Float(string='Max Experience (yrs)', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    salary_min = fields.Monetary(string='Salary From', currency_field='currency_id', tracking=True)
    salary_max = fields.Monetary(string='Salary To', currency_field='currency_id', tracking=True)
    hr_notes = fields.Text(string='HR Notes')

    # Approval trail
    requested_by_id = fields.Many2one(
        'res.users', string='Raised By', default=lambda self: self.env.user,
        readonly=True, copy=False)
    submitted_date = fields.Datetime(readonly=True, copy=False)
    hr_reviewed_by_id = fields.Many2one('res.users', string='Reviewed By (HR)', readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Approved By (CEO)', readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    reject_reason = fields.Text(string='Rejection Reason', copy=False)

    opening_ids = fields.One2many('manpower.job.opening', 'requirement_id', string='Job Openings')
    opening_count = fields.Integer(compute='_compute_opening_count')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('opening_ids')
    def _compute_opening_count(self):
        for rec in self:
            rec.opening_count = len(rec.opening_ids)

    @api.constrains('vacancies', 'experience_min', 'experience_max', 'salary_min', 'salary_max')
    def _check_values(self):
        for rec in self:
            if rec.vacancies < 1:
                raise ValidationError(_('Number of vacancies must be at least 1.'))
            if rec.experience_max and rec.experience_max < rec.experience_min:
                raise ValidationError(_('Maximum experience cannot be less than minimum experience.'))
            if rec.salary_max and rec.salary_max < rec.salary_min:
                raise ValidationError(_('Maximum salary cannot be less than minimum salary.'))

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('manpower.requirement') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        user = self.env.user
        # A department head who is not HR/CEO may only edit while in draft
        if (not self.env.su and user.has_group(GROUP_DEPT_HEAD)
                and not user.has_group(GROUP_HR) and not user.has_group(GROUP_CEO)):
            if any(rec.state != 'draft' for rec in self):
                raise UserError(_('You can only edit a requirement while it is in Draft.'))
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'rejected') for rec in self):
            raise UserError(_('Only draft or rejected requirements can be deleted.'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _check_group(self, xmlid):
        if not self.env.su and not self.env.user.has_group(xmlid):
            raise AccessError(_('You are not allowed to perform this action.'))

    def _notify_group(self, xmlid, message):
        """Post a chatter message that notifies every user of the given group."""
        users = self.env['res.users'].sudo().search([('share', '=', False)]).filtered(
            lambda u: u.has_group(xmlid))
        for rec in self:
            rec.message_post(
                body=message,
                partner_ids=users.partner_id.ids,
                subtype_xmlid='mail.mt_comment',
            )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_submit(self):
        """Department head -> HR."""
        self._check_group(GROUP_DEPT_HEAD)
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requirements can be submitted.'))
            if not rec.department_id:
                raise UserError(_('Please select a department before submitting.'))
        self.write({'state': 'hr_review', 'submitted_date': fields.Datetime.now()})
        self._notify_group(GROUP_HR, _('A new manpower requirement is waiting for HR review.'))

    def action_send_for_approval(self):
        """HR -> CEO, after experience and salary have been filled."""
        self._check_group(GROUP_HR)
        for rec in self:
            if rec.state != 'hr_review':
                raise UserError(_('Only requirements in HR Review can be sent for approval.'))
            if not rec.experience_max or not rec.salary_max:
                raise UserError(_(
                    'Please fill in the experience range and salary range before sending for approval.'))
        self.write({'state': 'pending_approval', 'hr_reviewed_by_id': self.env.user.id})
        self._notify_group(GROUP_CEO, _('A manpower requirement is waiting for your approval.'))

    def action_approve(self):
        """CEO approves."""
        self._check_group(GROUP_CEO)
        for rec in self:
            if rec.state != 'pending_approval':
                raise UserError(_('Only requirements pending approval can be approved.'))
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        self._notify_group(GROUP_HR, _('The requirement has been approved. You can now create the job opening.'))

    def action_reject(self):
        """HR (during review) or CEO (during approval) rejects."""
        for rec in self:
            if rec.state == 'hr_review':
                rec._check_group(GROUP_HR)
            elif rec.state == 'pending_approval':
                rec._check_group(GROUP_CEO)
            else:
                raise UserError(_('This requirement cannot be rejected in its current state.'))
            if not rec.reject_reason:
                raise UserError(_('Please enter a Rejection Reason before rejecting.'))
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self._check_group(GROUP_HR)
        self.write({'state': 'draft', 'approved_by_id': False, 'approved_date': False})

    def action_create_opening(self):
        """HR creates a job opening from an approved requirement."""
        self._check_group(GROUP_HR)
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('A job opening can only be created from an approved requirement.'))
        opening = self.env['manpower.job.opening'].create({
            'requirement_id': self.id,
            # `title` is required. Supply it at create time because stored computed
            # values are populated only after the record passes required-field checks.
            'title': self.job_title,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'manpower.job.opening',
            'res_id': opening.id,
            'view_mode': 'form',
        }

    def action_view_openings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Openings'),
            'res_model': 'manpower.job.opening',
            'view_mode': 'list,form',
            'domain': [('requirement_id', '=', self.id)],
            'context': {'default_requirement_id': self.id},
        }
