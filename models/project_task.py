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
    hiring_required = fields.Boolean(
        string='Hiring Required',
        default=False,
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

    @api.depends('requirement_ids')
    def _compute_requirement_count(self):
        for task in self:
            task.requirement_count = len(task.requirement_ids)

    @api.onchange('project_id')
    def _onchange_project_id_client(self):
        if self.project_id and self.project_id.partner_id and not self.client_id:
            self.client_id = self.project_id.partner_id

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
        if not self.hiring_required:
            raise UserError(_('Please check "Hiring Required" before submitting.'))
        self.write({'hiring_submitted': True})

        # Post update in chatter and notify assignees
        body = _('Hiring requirement has been submitted. HR can now create the hiring request.')
        self.message_post(body=body, subtype_xmlid='mail.mt_comment')
        return True

    def action_create_hiring_request(self):
        """HR creates a manpower requisition from this task."""
        self.ensure_one()
        if not self.hiring_required:
            raise UserError(_('Hiring is not marked as required for this task.'))
        if not self.hiring_submitted:
            raise UserError(_('Please submit the hiring requirement before creating a request.'))

        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        dept_id = employee.department_id.id if employee and employee.department_id else False
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
                'default_state': 'hr_review',
                'default_submitted_date': fields.Datetime.now(),
                'default_reason': 'project',
                'default_reason_note': _('Hiring requested from Task: %s (Project: %s)') % (
                    self.name, self.project_id.name if self.project_id else _('None')
                ),
                'default_department_id': dept_id,
            },
        }

    def action_view_hiring_requests(self):
        """Smart button action to view all linked manpower requirements."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('manpower_requisition.action_manpower_requirement')
        action['domain'] = [('task_id', '=', self.id)]
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        dept_id = employee.department_id.id if employee and employee.department_id else False
        client = self.client_id or self.partner_id or (self.project_id and self.project_id.partner_id) or False
        action['context'] = {
            'default_project_id': self.project_id.id if self.project_id else False,
            'default_task_id': self.id,
            'default_client_id': client.id if client else False,
            'default_job_title': self.name,
            'default_request_type': 'hiring',
            'default_reason': 'project',
            'default_department_id': dept_id,
        }
        return action
