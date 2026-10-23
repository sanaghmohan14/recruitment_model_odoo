from odoo import _, api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    hiring_required = fields.Boolean(
        string='Hiring Required',
        default=False,
        compute='_compute_hiring_required',
        store=True,
        readonly=False,
        tracking=True,
        copy=False,
        help='Enable hiring requirement workflow for this project.'
    )
    requirement_ids = fields.One2many(
        'manpower.requirement',
        'project_id',
        string='Hiring Requests'
    )
    requirement_count = fields.Integer(
        string='Hiring Requests Count',
        compute='_compute_requirement_count'
    )

    @api.depends('name')
    def _compute_hiring_required(self):
        for project in self:
            if project.name and 'hiring' in project.name.lower():
                project.hiring_required = True
            elif not project.hiring_required:
                project.hiring_required = False

    task_user_ids = fields.Many2many(
        'res.users',
        string='Task Assignees',
        compute='_compute_task_user_ids',
        search='_search_task_user_ids',
        help='Users assigned to tasks in this project.'
    )

    @api.depends('requirement_ids')
    def _compute_requirement_count(self):
        for project in self:
            project.requirement_count = len(project.requirement_ids)

    @api.depends('task_ids.user_ids')
    def _compute_task_user_ids(self):
        for project in self:
            project.task_user_ids = project.task_ids.user_ids

    def _search_task_user_ids(self, operator, value):
        tasks = self.env['project.task'].sudo().search([('user_ids', operator, value)])
        project_ids = tasks.mapped('project_id').ids
        return [('id', 'in', project_ids)]

    def action_create_hiring_request(self):
        """Action for 'Hiring Required' button on the project card to create a hiring request."""
        self.ensure_one()
        client = self.partner_id or False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create Hiring Request'),
            'res_model': 'manpower.requirement',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_project_id': self.id,
                'default_client_id': client.id if client else False,
                'default_request_type': 'hiring',
                'default_state': 'draft',
                'default_reason': 'project',
                'default_reason_note': _('Hiring requested from Project: %s') % self.name,
            },
        }

    def action_view_hiring_requests(self):
        """Smart button or card action to view all hiring requests for this project."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('manpower_requisition.action_manpower_requirement')
        action['domain'] = [('project_id', '=', self.id)]
        client = self.partner_id or False
        action['context'] = {
            'default_project_id': self.id,
            'default_client_id': client.id if client else False,
            'default_request_type': 'hiring',
            'default_reason': 'project',
        }
        return action

    def action_toggle_hiring_required(self):
        """Toggle hiring_required on/off directly from card or form."""
        for project in self:
            new_val = not project.hiring_required
            project.hiring_required = new_val
            tasks = self.env['project.task'].with_context(active_test=False).search([('project_id', '=', project.id)])
            tasks.write({'hiring_required': new_val})
        return True

    def write(self, vals):
        res = super().write(vals)
        if 'hiring_required' in vals:
            for project in self:
                tasks = self.env['project.task'].with_context(active_test=False).search([('project_id', '=', project.id)])
                tasks.write({'hiring_required': vals['hiring_required']})
        return res


