from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    task_user_ids = fields.Many2many(
        'res.users',
        string='Task Assignees',
        compute='_compute_task_user_ids',
        search='_search_task_user_ids',
        help='Users assigned to tasks in this project.'
    )

    @api.depends('task_ids.user_ids')
    def _compute_task_user_ids(self):
        for project in self:
            project.task_user_ids = project.task_ids.user_ids

    def _search_task_user_ids(self, operator, value):
        tasks = self.env['project.task'].sudo().search([('user_ids', operator, value)])
        project_ids = tasks.mapped('project_id').ids
        return [('id', 'in', project_ids)]
