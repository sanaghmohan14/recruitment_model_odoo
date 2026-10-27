from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

GROUP_DEPT_HEAD = 'manpower_requisition.group_dept_head'
GROUP_PROJECT_MANAGER = 'manpower_requisition.group_project_manager'
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
        ('pm_review', 'Project Manager Review'),
        ('hr_review', 'HR Review'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True, copy=False, required=True)
    request_type = fields.Selection([
        ('hiring', 'Hiring Request'),
        ('client', 'Project Requirement'),
        ('internal', 'Internal Requirement'),
    ], string='Request Type', default='hiring', required=True, tracking=True,
       copy=False)

    def _default_project_id(self):
        project = self.env['project.project'].search([('hiring_required', '=', True)], limit=1)
        if not project:
            project = self.env['project.project'].search([('name', '=ilike', 'Hiring%')], limit=1)
        if not project:
            project = self.env['project.project'].sudo().create({
                'name': 'Hiring & Recruitment',
                'hiring_required': True,
            })
        return project.id if project else False

    # Project and Task details
    project_id = fields.Many2one(
        'project.project', string='Project',
        default=_default_project_id,
        tracking=True
    )
    task_id = fields.Many2one(
        'project.task', string='Job Role',
        domain="[('project_id', '=', project_id)] if project_id else []",
        tracking=True)
    client_id = fields.Many2one(
        'res.partner', string='Client', tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Customer',
        related='client_id', store=True, readonly=True)

    # Client contact info (from website or client requirement)
    client_contact_name = fields.Char(string='Contact Person', tracking=True)
    client_company_name = fields.Char(string='Company Name', tracking=True)
    client_email = fields.Char(string='Email', tracking=True)
    client_phone = fields.Char(string='Phone', tracking=True)
    client_address = fields.Text(string='Address', tracking=True)

    # Requirement details
    job_title = fields.Char(string='Position', required=True, tracking=True)
    vacancies = fields.Integer(string='Number of Vacancies', default=1, tracking=True)
    qualification = fields.Char(string='Qualification')
    skill_ids = fields.Many2many('manpower.skill', string='Skills')
    location = fields.Char(string='Location')
    closing_date = fields.Date(string='Target / Closing Date', tracking=True)
    job_description = fields.Text(string='Job Description / Scope')
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

    # Experience & Salary (Reviewed by Project Manager & HR)
    experience_min = fields.Float(string='Min Experience (yrs)', tracking=True)
    experience_max = fields.Float(string='Max Experience (yrs)', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    salary_min = fields.Monetary(string='Salary From', currency_field='currency_id', tracking=True)
    salary_max = fields.Monetary(string='Salary To', currency_field='currency_id', tracking=True)
    pm_notes = fields.Text(string='PM Notes')
    hr_notes = fields.Text(string='HR Notes')

    # Approval trail
    requested_by_id = fields.Many2one(
        'res.users', string='Raised By', default=lambda self: self.env.user,
        readonly=True, copy=False)
    submitted_date = fields.Datetime(readonly=True, copy=False)
    pm_reviewed_by_id = fields.Many2one('res.users', string='Reviewed By (Project Manager)', readonly=True, copy=False)
    hr_reviewed_by_id = fields.Many2one('res.users', string='Processed By (HR)', readonly=True, copy=False)
    approved_by_id = fields.Many2one('res.users', string='Approved By (CEO)', readonly=True, copy=False)
    approved_date = fields.Datetime(readonly=True, copy=False)
    reject_reason = fields.Text(string='Rejection Reason', copy=False)

    opening_ids = fields.One2many('manpower.job.opening', 'requirement_id', string='Job Openings')
    opening_count = fields.Integer(compute='_compute_opening_count')
    application_ids = fields.One2many('manpower.application', 'requirement_id', string='Applications')
    application_count = fields.Integer(compute='_compute_application_count', string='Applications')
    new_application_count = fields.Integer(compute='_compute_application_count', string='New Applications')
    in_progress_application_count = fields.Integer(compute='_compute_application_count', string='In Progress')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    is_ceo = fields.Boolean(compute='_compute_user_role')
    is_hr = fields.Boolean(compute='_compute_user_role')
    is_pm = fields.Boolean(compute='_compute_user_role')

    @api.depends_context('uid')
    def _compute_user_role(self):
        user = self.env.user
        is_ceo = user.has_group(GROUP_CEO)
        is_hr = user.has_group(GROUP_HR) and not is_ceo
        is_pm = user.has_group(GROUP_PROJECT_MANAGER) and not is_ceo
        for req in self:
            req.is_ceo = is_ceo
            req.is_hr = is_hr
            req.is_pm = is_pm

    @api.depends('opening_ids')
    def _compute_opening_count(self):
        for rec in self:
            rec.opening_count = len(rec.opening_ids)

    @api.depends('application_ids', 'application_ids.stage')
    def _compute_application_count(self):
        for rec in self:
            rec.application_count = len(rec.application_ids)
            rec.new_application_count = len(rec.application_ids.filtered(lambda app: app.stage == 'new'))
            rec.in_progress_application_count = len(rec.application_ids.filtered(
                lambda app: app.stage not in ('new', 'contract_signed', 'cancelled')))

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id:
            if self.task_id.project_id and not self.project_id:
                self.project_id = self.task_id.project_id
            self.job_title = self.task_id.name
            if self.task_id.client_id:
                self.client_id = self.task_id.client_id
            elif self.task_id.partner_id:
                self.client_id = self.task_id.partner_id

    @api.onchange('job_title')
    def _onchange_job_title(self):
        if self.job_title and not self.task_id:
            proj_id = self.project_id.id if self.project_id else self._default_project_id()
            if proj_id:
                task = self.env['project.task'].search([
                    ('project_id', '=', proj_id),
                    ('name', '=ilike', self.job_title.strip()),
                ], limit=1)
                if task:
                    self.task_id = task.id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.partner_id and not self.client_id:
            self.client_id = self.project_id.partner_id

    @api.model
    def _format_partner_address(self, partner):
        if not partner:
            return ''
        addr_text = ''
        if hasattr(partner, '_display_address'):
            addr_text = partner._display_address().strip()
        if not addr_text:
            parts = [
                partner.street,
                partner.street2,
                ", ".join(filter(None, [partner.city, partner.state_id.name, partner.zip])),
                partner.country_id.name,
            ]
            addr_text = "\n".join([p for p in parts if p and p.strip()])
        return addr_text

    @api.depends('name', 'client_id', 'client_company_name', 'job_title')
    def _compute_display_name(self):
        for rec in self:
            parts = [rec.name or '']
            cname = rec.client_id.name or rec.client_company_name
            if cname:
                parts.append(cname)
            if rec.job_title:
                parts.append(rec.job_title)
            rec.display_name = " - ".join([p for p in parts if p])

    @api.onchange('client_id')
    def _onchange_client_id(self):
        if self.client_id:
            partner = self.client_id
            self.client_email = partner.email or ''
            self.client_phone = partner.phone or getattr(partner, 'mobile', '') or ''
            self.client_address = self._format_partner_address(partner)
            self.client_company_name = (
                partner.parent_id.name if partner.parent_id
                else (partner.name if partner.is_company else '')
            )
            self.client_contact_name = partner.name if not partner.is_company else ''
        else:
            self.client_email = False
            self.client_phone = False
            self.client_address = False
            self.client_company_name = False
            self.client_contact_name = False

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
        if not self.env.su and not self.env.user.has_group(GROUP_PROJECT_MANAGER):
            raise AccessError(_('Only Project Managers can create hiring requests.'))
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('manpower.requirement') or 'New'
            if not vals.get('project_id'):
                default_proj = self._default_project_id()
                if default_proj:
                    vals['project_id'] = default_proj

            # Automatically fill Job Role (task_id / job_title)
            proj_id = vals.get('project_id')
            if not vals.get('task_id') and vals.get('job_title'):
                job_title_clean = vals['job_title'].strip()
                Task = self.env['project.task'].sudo()
                task = False
                if proj_id:
                    task = Task.search([
                        ('project_id', '=', proj_id),
                        ('name', '=ilike', job_title_clean)
                    ], limit=1)
                if not task and proj_id:
                    task = Task.create({
                        'name': job_title_clean,
                        'project_id': proj_id,
                        'partner_id': vals.get('client_id') or False,
                        'client_id': vals.get('client_id') or False,
                        'hiring_required': True,
                        'hiring_submitted': True,
                    })
                if task:
                    vals['task_id'] = task.id
            elif vals.get('task_id') and not vals.get('job_title'):
                task = self.env['project.task'].browse(vals['task_id'])
                if task.exists():
                    vals['job_title'] = task.name

            # Automatically fill Client contact info if client_id is provided
            if vals.get('client_id'):
                partner = self.env['res.partner'].browse(vals['client_id'])
                if partner.exists():
                    if not vals.get('client_email') and partner.email:
                        vals['client_email'] = partner.email
                    partner_phone = partner.phone or getattr(partner, 'mobile', '')
                    if not vals.get('client_phone') and partner_phone:
                        vals['client_phone'] = partner_phone
                    if not vals.get('client_address'):
                        vals['client_address'] = self._format_partner_address(partner)
                    if not vals.get('client_company_name'):
                        vals['client_company_name'] = partner.parent_id.name if partner.parent_id else (partner.name if partner.is_company else '')
                    if not vals.get('client_contact_name') and not partner.is_company:
                        vals['client_contact_name'] = partner.name

            if vals.get('state') == 'pending_approval' and not vals.get('submitted_date'):
                vals['submitted_date'] = fields.Datetime.now()
        return super().create(vals_list)

    def write(self, vals):
        user = self.env.user
        if (not self.env.su and user.has_group(GROUP_DEPT_HEAD)
                and not user.has_group(GROUP_PROJECT_MANAGER)
                and not user.has_group(GROUP_HR) and not user.has_group(GROUP_CEO)):
            raise AccessError(_('Consultants are not allowed to modify hiring requests.'))
        if vals.get('client_id'):
            partner = self.env['res.partner'].browse(vals['client_id'])
            if partner.exists():
                if 'client_email' not in vals and partner.email:
                    vals['client_email'] = partner.email
                partner_phone = partner.phone or getattr(partner, 'mobile', '')
                if 'client_phone' not in vals and partner_phone:
                    vals['client_phone'] = partner_phone
                if 'client_address' not in vals:
                    vals['client_address'] = self._format_partner_address(partner)
        return super().write(vals)

    def unlink(self):
        if any(rec.state not in ('draft', 'rejected') for rec in self):
            raise UserError(_('Only draft or rejected requirements can be deleted.'))
        return super().unlink()

    # Helpers
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

    # Workflow
    def action_submit(self):
        """Submit requirement to CEO for approval."""
        return self.action_send_for_approval()

    def action_send_for_approval(self):
        """Project Manager -> CEO for approval."""
        self._check_group(GROUP_PROJECT_MANAGER)
        for rec in self:
            if rec.state not in ('draft', 'pm_review'):
                raise UserError(_('Only draft requirements can be sent for approval.'))
            if not rec.experience_max or not rec.salary_max:
                raise UserError(_('Please fill in the experience range and salary range before sending for approval.'))
        self.write({
            'state': 'pending_approval',
            'submitted_date': fields.Datetime.now(),
            'pm_reviewed_by_id': self.env.user.id,
        })
        self._notify_group(GROUP_CEO, _('A manpower requirement has been submitted by the Project Manager and is waiting for your approval.'))

    def action_approve(self):
        """CEO approves and forwards to HR."""
        self._check_group(GROUP_CEO)
        for rec in self:
            if rec.state != 'pending_approval':
                raise UserError(_('Only requirements pending approval can be approved.'))
        self.write({
            'state': 'approved',
            'approved_by_id': self.env.user.id,
            'approved_date': fields.Datetime.now(),
        })
        self._notify_group(GROUP_HR, _('The requirement has been approved by the CEO and forwarded to HR. You can now create the job opening.'))

    def action_reject(self):
        """Open the rejection-reason wizard for PM or CEO review."""
        self.ensure_one()
        if self.state in ('draft', 'pm_review'):
            self._check_group(GROUP_PROJECT_MANAGER)
        elif self.state == 'pending_approval':
            self._check_group(GROUP_CEO)
        else:
            raise UserError(_('This requirement cannot be rejected in its current state.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Manpower Requirement'),
            'res_model': 'manpower.requirement.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_requirement_id': self.id},
        }

    def action_reset_draft(self):
        self._check_group(GROUP_PROJECT_MANAGER)
        self.write({'state': 'draft', 'approved_by_id': False, 'approved_date': False, 'pm_reviewed_by_id': False})

    def action_create_opening(self):
        """HR creates a job opening from an approved requirement."""
        self._check_group(GROUP_HR)
        if self.env.user.has_group(GROUP_CEO) and not self.env.su:
            raise AccessError(_('Only HR users can create a job opening.'))
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('A job opening can only be created from an approved requirement.'))
        opening = self.env['manpower.job.opening'].create({
            'requirement_id': self.id,
            # Copy the approved requirement so the opening is fully populated as
            # soon as its form is displayed.
            'title': self.job_title,
            'vacancies': self.vacancies,
            'location': self.location,
            'qualification': self.qualification,
            'skill_ids': [(6, 0, self.skill_ids.ids)],
            'experience_min': self.experience_min,
            'experience_max': self.experience_max,
            'currency_id': self.currency_id.id,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'closing_date': self.closing_date,
            'description': self.job_description or '',
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

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Applications - %s') % (self.name or self.job_title),
            'res_model': 'manpower.application',
            'view_mode': 'kanban,list,form',
            'domain': [('requirement_id', '=', self.id)],
            'context': {
                'default_requirement_id': self.id,
                'search_default_group_by_stage': 1,
            },
        }

    def action_open_client_update_wizard(self):
        """Open the wizard to send stage status update to the client."""
        self.ensure_one()
        if not self.client_id:
            raise UserError(_('Please select a client for this requirement before sending an update.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Update to Client'),
            'res_model': 'manpower.requirement.client.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_requirement_id': self.id,
                'default_client_id': self.client_id.id,
            },
        }
