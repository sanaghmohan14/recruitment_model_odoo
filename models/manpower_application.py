from odoo import api, fields, models


APPLICATION_STAGES = [
    ('new', 'New'),
    ('qualification', 'Qualification'),
    ('first_interview', 'First Interview'),
    ('second_interview', 'Second Interview'),
    ('contract_proposal', 'Contract Proposal'),
    ('contract_signed', 'Contract Signed'),
]
APPLICATION_STAGE_SEQUENCE = [stage[0] for stage in APPLICATION_STAGES]


class ManpowerApplication(models.Model):
    """Candidate application for a client job opening, independent of hr_recruitment."""

    _name = 'manpower.application'
    _description = 'Manpower Application'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Application Reference', default='New', readonly=True,
                       copy=False, tracking=True)
    applicant_name = fields.Char(string='Applicant Name', required=True, tracking=True)
    job_opening_id = fields.Many2one(
        'manpower.job.opening', string='Job Position', required=True,
        ondelete='restrict', tracking=True)
    stage = fields.Selection(
        APPLICATION_STAGES, string='Stage', default='new', required=True, tracking=True,
        group_expand='_read_group_stage')

    # Applicant details
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    date_of_birth = fields.Date(string='Date of Birth')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ])
    address = fields.Text(string='Address')
    photo = fields.Image(string='Photo', max_width=1920, max_height=1920)

    # Compensation
    currency_id = fields.Many2one(
        'res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    current_salary = fields.Monetary(string='Current Salary', currency_field='currency_id')
    expected_salary = fields.Monetary(string='Expected Salary', currency_field='currency_id')
    notice_period = fields.Char(string='Notice Period')

    # Academic details
    highest_qualification = fields.Char(string='Highest Qualification')
    specialization = fields.Char(string='Specialization')
    institution = fields.Char(string='Institution')
    graduation_year = fields.Char(string='Graduation Year')

    # Experience details
    total_experience = fields.Float(string='Total Experience (Years)')
    current_employer = fields.Char(string='Current Employer')
    current_designation = fields.Char(string='Current Designation')
    experience_details = fields.Text(string='Experience Details')

    # Identity and bank details
    aadhaar_number = fields.Char(string='Aadhaar Number')
    pan_number = fields.Char(string='PAN Number')
    bank_name = fields.Char(string='Bank Name')
    account_holder_name = fields.Char(string='Account Holder Name')
    account_number = fields.Char(string='Account Number')
    ifsc_code = fields.Char(string='IFSC Code')

    # Documents
    aadhaar_document = fields.Binary(string='Aadhaar Card')
    aadhaar_document_filename = fields.Char()
    pan_document = fields.Binary(string='PAN Card')
    pan_document_filename = fields.Char()
    bank_document = fields.Binary(string='Bank Document')
    bank_document_filename = fields.Char()
    experience_document = fields.Binary(string='Experience Document')
    experience_document_filename = fields.Char()
    resume = fields.Binary(string='Resume')
    resume_filename = fields.Char()
    notes = fields.Html(string='Notes')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('manpower.application') or 'New'
        return super().create(vals_list)

    def action_next_stage(self):
        """Advance the application through the recruitment process one stage at a time."""
        for rec in self:
            stage_index = APPLICATION_STAGE_SEQUENCE.index(rec.stage)
            if stage_index < len(APPLICATION_STAGE_SEQUENCE) - 1:
                rec.stage = APPLICATION_STAGE_SEQUENCE[stage_index + 1]

    def action_previous_stage(self):
        """Return the application to the previous stage."""
        for rec in self:
            stage_index = APPLICATION_STAGE_SEQUENCE.index(rec.stage)
            if stage_index > 0:
                rec.stage = APPLICATION_STAGE_SEQUENCE[stage_index - 1]

    @api.model
    def _read_group_stage(self, stages, domain):
        """Always show the complete application pipeline in its defined order."""
        return APPLICATION_STAGE_SEQUENCE
