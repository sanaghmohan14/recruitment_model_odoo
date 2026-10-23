import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError


APPLICATION_STAGES = [
    ('new', 'New'),
    ('qualification', 'Qualification'),
    ('first_interview', 'Internal Interview'),
    ('second_interview', 'Manager Interview'),
    ('third_interview', 'Client Interview'),
    ('contract_proposal', 'Contract Proposal'),
    ('contract_signed', 'Contract Signed'),
    ('cancelled', 'Cancelled'),
]
APPLICATION_STAGE_SEQUENCE = [stage[0] for stage in APPLICATION_STAGES]
INTERVIEW_SCORE_SELECTION = [
    ('0', 'Not Rated'),
    ('1', '1 Star'),
    ('2', '2 Stars'),
    ('3', '3 Stars'),
    ('4', '4 Stars'),
    ('5', '5 Stars'),
]


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
    client_id = fields.Many2one(
        'res.partner', string='Client', related='job_opening_id.client_id',
        store=True, readonly=True)
    stage = fields.Selection(
        APPLICATION_STAGES, string='Stage', default='new', required=True, tracking=True,
        group_expand='_read_group_stage')
    interest_token = fields.Char(default=lambda self: str(uuid.uuid4()), readonly=True, copy=False)
    candidate_interest = fields.Selection([
        ('pending', 'Pending'),
        ('interested', 'Interested'),
    ], default='pending', readonly=True, copy=False, tracking=True)
    reject_reason = fields.Text(string='Rejection Reason', copy=False, tracking=True)

    # Interview performance ratings, independently recorded at each stage.
    first_interview_score = fields.Selection(
        INTERVIEW_SCORE_SELECTION, string='Internal Interview Score', default='0', tracking=True)
    second_interview_score = fields.Selection(
        INTERVIEW_SCORE_SELECTION, string='Manager Interview Score', default='0', tracking=True)
    third_interview_score = fields.Selection(
        INTERVIEW_SCORE_SELECTION, string='Client Interview Score', default='0', tracking=True)

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
            if not vals.get('interest_token'):
                vals['interest_token'] = str(uuid.uuid4())
        return super().create(vals_list)

    def action_open_stage_email_wizard(self):
        self.ensure_one()
        email_type_by_stage = {
            'qualification': 'qualification',
            'first_interview': 'first_interview',
            'second_interview': 'second_interview',
            'contract_proposal': 'selection',
            'contract_signed': 'offer',
        }
        email_type = email_type_by_stage.get(self.stage)
        if not email_type:
            raise UserError(_('There is no email template for the New stage.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Application Email'),
            'res_model': 'manpower.application.email.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_application_id': self.id,
                'default_email_type': email_type,
            },
        }

    def action_next_stage(self):
        """Advance to the next configured application stage."""
        for rec in self:
            stage_index = APPLICATION_STAGE_SEQUENCE.index(rec.stage)
            if stage_index < len(APPLICATION_STAGE_SEQUENCE) - 1:
                rec.stage = APPLICATION_STAGE_SEQUENCE[stage_index + 1]

    def action_reject(self):
        """Open the rejection-reason wizard for an interviewed application."""
        self.ensure_one()
        if self.stage not in ('first_interview', 'second_interview'):
            raise UserError(_('An application can only be rejected after an interview.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Application'),
            'res_model': 'manpower.application.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_application_id': self.id},
        }

    def action_open_client_update_wizard(self):
        """Open the wizard to send candidate stage update to the client."""
        self.ensure_one()
        client = (
            self.client_id
            or (self.job_opening_id and self.job_opening_id.client_id)
            or (self.job_opening_id and self.job_opening_id.requirement_id and self.job_opening_id.requirement_id.client_id)
        )
        if not client:
            raise UserError(_('No client is associated with this job opening / requirement.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Update to Client'),
            'res_model': 'manpower.application.client.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_application_id': self.id,
                'default_client_id': client.id,
            },
        }

    @api.model
    def _read_group_stage(self, stages, domain):
        """Always show the complete application pipeline in its defined order."""
        return APPLICATION_STAGE_SEQUENCE
