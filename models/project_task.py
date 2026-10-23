from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        tracking=True,
        help='Client for this task / hiring request.'
    )
    project_hiring_required = fields.Boolean(
        related='project_id.hiring_required',
        string='Project Hiring Required',
        readonly=True
    )
    hiring_required = fields.Boolean(
        string='Hiring Required',
        default=False,
        compute='_compute_hiring_required',
        store=True,
        readonly=False,
        tracking=True,
        copy=False,
        help='Indicate whether hiring/manpower is required for this task.'
    )
    hiring_submitted = fields.Boolean(
        string='Hiring Submitted',
        default=False,
        tracking=True,
        copy=False,
        help='Indicates whether hiring has been submitted to HR.'
    )
    requirement_ids = fields.One2many(
        'manpower.requirement',
        'task_id',
        string='Hiring Requests'
    )
    requirement_count = fields.Integer(
        string='Hiring Requests Count',
        compute='_compute_requirement_count'
    )

    @api.depends('project_id', 'project_id.hiring_required')
    def _compute_hiring_required(self):
        for task in self:
            if task.project_id:
                task.hiring_required = bool(task.project_id.hiring_required)
            elif not task.hiring_required:
                task.hiring_required = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('project_id') and 'hiring_required' not in vals:
                project = self.env['project.project'].browse(vals['project_id'])
                if project.exists() and project.hiring_required:
                    vals['hiring_required'] = True
        return super().create(vals_list)

    def write(self, vals):
        if 'project_id' in vals and vals['project_id'] and 'hiring_required' not in vals:
            project = self.env['project.project'].browse(vals['project_id'])
            if project.exists():
                vals['hiring_required'] = bool(project.hiring_required)
        return super().write(vals)

    @api.depends('requirement_ids')
    def _compute_requirement_count(self):
        for task in self:
            task.requirement_count = len(task.sudo().requirement_ids)

    @api.onchange('project_id')
    def _onchange_project_id_client(self):
        if self.project_id and self.project_id.partner_id and not self.client_id:
            self.client_id = self.project_id.partner_id
        if self.project_id:
            self.hiring_required = self.project_id.hiring_required

    @api.onchange('partner_id')
    def _onchange_partner_id_client(self):
        if self.partner_id and not self.client_id:
            self.client_id = self.partner_id

    @api.onchange('client_id')
    def _onchange_client_id(self):
        if self.client_id and not self.partner_id:
            self.partner_id = self.client_id

    @api.onchange('hiring_required')
    def _onchange_hiring_required(self):
        if not self.hiring_required:
            self.hiring_submitted = False

    def action_submit_hiring(self):
        """Admin or task creator/assigner submits the hiring requirement to HR."""
        self.ensure_one()
        self.write({'hiring_submitted': True})
        body = _('Hiring requirement has been submitted. HR can now create the hiring request.')
        self.message_post(body=body, subtype_xmlid='mail.mt_comment')
        return True

    def action_create_hiring_request(self):
        """Create a manpower requisition from this task (Project Manager only)."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group('manpower_requisition.group_project_manager'):
            raise UserError(_('Only a Project Manager can create a hiring request.'))
        if not self.hiring_required and not (self.project_id and self.project_id.hiring_required):
            raise UserError(_('Hiring is not marked as required for this project/task.'))

        if not self.hiring_required and self.project_id and self.project_id.hiring_required:
            self.write({'hiring_required': True})

        client = self.client_id or self.partner_id or (self.project_id and self.project_id.partner_id) or False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Hiring Request'),
            'res_model': 'manpower.requirement',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.project_id.id if self.project_id else False,
                'default_task_id': self.id,
                'default_client_id': client.id if client else False,
                'default_job_title': self.name,
                'default_request_type': 'hiring',
                'default_state': 'draft',
                'default_reason': 'project',
                'default_reason_note': _('Hiring requested from Task: %s (Project: %s)') % (
                    self.name, self.project_id.name if self.project_id else _('None')
                ),
            },
        }

    def action_view_hiring_requests(self):
        """Smart button action to view all linked manpower requirements."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('manpower_requisition.action_manpower_requirement')
        action['domain'] = [('task_id', '=', self.id)]
        client = self.client_id or self.partner_id or (self.project_id and self.project_id.partner_id) or False
        action['context'] = {
            'default_project_id': self.project_id.id if self.project_id else False,
            'default_task_id': self.id,
            'default_client_id': client.id if client else False,
            'default_job_title': self.name,
            'default_request_type': 'hiring',
            'default_reason': 'project',
        }
        return action
