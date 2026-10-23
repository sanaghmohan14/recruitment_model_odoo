from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ManpowerPostingChannel(models.Model):
    _name = 'manpower.posting.channel'
    _description = 'Job Posting Channel'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class ManpowerJobOpening(models.Model):
    """Standalone job opening. Intentionally NOT linked to hr_recruitment."""
    _name = 'manpower.job.opening'
    _description = 'Job Opening'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    _rec_name = 'title'

    name = fields.Char(string='Reference', default='New', readonly=True, copy=False)
    application_ids = fields.One2many('manpower.application', 'job_opening_id', string='Applications')
    application_count = fields.Integer(compute='_compute_application_count')
    new_application_count = fields.Integer(compute='_compute_application_count', string='New Applications')
    in_progress_application_count = fields.Integer(compute='_compute_application_count', string='In Progress')
    requirement_id = fields.Many2one(
        'manpower.requirement', string='Requirement', required=True,
        domain="[('state', '=', 'approved')]", ondelete='restrict', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, copy=False, required=True)

    # Copied from the requirement, editable by HR
    title = fields.Char(string='Job Title', compute='_compute_from_requirement',
                        store=True, readonly=False, required=True, tracking=True)
    department_id = fields.Many2one('hr.department', compute='_compute_from_requirement',
                                    store=True, readonly=False)
    project_id = fields.Many2one('project.project', related='requirement_id.project_id', store=True, string='Project')
    task_id = fields.Many2one('project.task', related='requirement_id.task_id', store=True, string='Job Role')
    client_id = fields.Many2one('res.partner', related='requirement_id.client_id', store=True, string='Client / Partner')
    vacancies = fields.Integer(compute='_compute_from_requirement', store=True, readonly=False)
    location = fields.Char(compute='_compute_from_requirement', store=True, readonly=False)
    qualification = fields.Char(compute='_compute_from_requirement', store=True, readonly=False)
    skill_ids = fields.Many2many('manpower.skill', string='Skills')
    experience_min = fields.Float(compute='_compute_from_requirement', store=True, readonly=False)
    experience_max = fields.Float(compute='_compute_from_requirement', store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', compute='_compute_from_requirement',
                                  store=True, readonly=False)
    salary_min = fields.Monetary(currency_field='currency_id', compute='_compute_from_requirement',
                                 store=True, readonly=False)
    salary_max = fields.Monetary(currency_field='currency_id', compute='_compute_from_requirement',
                                 store=True, readonly=False)

    # Job description
    description = fields.Html(string='Job Description')
    jd_approved = fields.Boolean(string='JD Approved')

    # Posting
    channel_ids = fields.Many2many('manpower.posting.channel', string='Posting Channels')
    posting_date = fields.Date(readonly=True, copy=False)
    closing_date = fields.Date(string='Application Closing Date', tracking=True)
    is_expired = fields.Boolean(
        string='Is Expired',
        compute='_compute_is_expired',
        help='Whether application closing date has passed.'
    )
    published_by_id = fields.Many2one('res.users', readonly=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.depends('closing_date')
    def _compute_is_expired(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_expired = bool(rec.closing_date and rec.closing_date < today)

    def _get_website_url(self):
        self.ensure_one()
        return '/manpower/jobs/%s' % self.id

    def action_view_website(self):
        self.ensure_one()
        if self.state != 'published':
            raise ValidationError(_('Only published job openings can be viewed on the website.'))
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return {
            'type': 'ir.actions.act_url',
            'url': '%s%s' % (base_url.rstrip('/'), self._get_website_url()),
            'target': 'new',
        }

    @api.depends('application_ids', 'application_ids.stage')
    def _compute_application_count(self):
        for rec in self:
            rec.application_count = len(rec.application_ids)
            rec.new_application_count = len(rec.application_ids.filtered(lambda app: app.stage == 'new'))
            rec.in_progress_application_count = len(rec.application_ids.filtered(
                lambda app: app.stage not in ('new', 'contract_signed')))

    def action_view_applications(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Applications'),
            'res_model': 'manpower.application',
            'view_mode': 'kanban,list,form',
            'domain': [('job_opening_id', '=', self.id)],
            'context': {'default_job_opening_id': self.id, 'group_by': 'stage'},
        }

    @api.depends('requirement_id')
    def _compute_from_requirement(self):
        for rec in self:
            req = rec.requirement_id
            rec.title = req.job_title or rec.title
            rec.department_id = req.department_id
            rec.vacancies = req.vacancies
            rec.location = req.location
            rec.qualification = req.qualification
            rec.experience_min = req.experience_min
            rec.experience_max = req.experience_max
            rec.currency_id = req.currency_id
            rec.salary_min = req.salary_min
            rec.salary_max = req.salary_max

    @api.constrains('requirement_id', 'vacancies', 'state')
    def _check_requirement(self):
        for rec in self:
            req = rec.requirement_id
            if req.state != 'approved':
                raise ValidationError(_('A job opening requires an approved requirement.'))
            others = req.opening_ids.filtered(lambda o: o.state != 'cancelled')
            if sum(others.mapped('vacancies')) > req.vacancies:
                raise ValidationError(_(
                    'Total vacancies across openings (%(total)s) exceed the approved '
                    'vacancies (%(approved)s) of requirement %(ref)s.',
                    total=sum(others.mapped('vacancies')),
                    approved=req.vacancies, ref=req.name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('manpower.job.opening') or 'New'
        return super().create(vals_list)

    def action_publish(self):
        for rec in self:
            if not rec.description:
                raise ValidationError(_('Please write the Job Description before publishing.'))
            if not rec.channel_ids:
                raise ValidationError(_('Please select at least one posting channel.'))
        self.write({
            'state': 'published',
            'posting_date': fields.Date.context_today(self),
            'published_by_id': self.env.user.id,
        })

    def action_close(self):
        self.write({'state': 'closed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
