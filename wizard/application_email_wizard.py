from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


EMAIL_TYPES = [
    ('qualification', 'Qualification Shortlist'),
    ('first_interview', 'First Interview'),
    ('second_interview', 'Second Interview'),
    ('selection', 'Selection Confirmation'),
    ('offer', 'Offer Letter'),
]


class ManpowerApplicationEmailWizard(models.TransientModel):
    _name = 'manpower.application.email.wizard'
    _description = 'Send Application Stage Email'

    application_id = fields.Many2one('manpower.application', required=True, readonly=True)
    email_type = fields.Selection(EMAIL_TYPES, required=True, readonly=True)
    email_to = fields.Char(string='Recipient', required=True)
    interview_date = fields.Date(string='Interview Date')
    interview_time = fields.Float(string='Interview Time')
    subject = fields.Char(required=True)
    body = fields.Html(required=True, sanitize_style=True)

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        application = self.env['manpower.application'].browse(
            self.env.context.get('default_application_id')).exists()
        email_type = self.env.context.get('default_email_type')
        if application:
            values['application_id'] = application.id
            values['email_to'] = application.email
        if email_type:
            values['email_type'] = email_type
        if application and email_type:
            values.update(self._email_content(application, email_type))
        return values

    def _interest_url(self, application):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return '%s/manpower/application/%s/interest/%s' % (
            base_url.rstrip('/'), application.id, application.interest_token)

    def _email_content(self, application, email_type):
        position = application.job_opening_id.title
        applicant = application.applicant_name
        contents = {
            'qualification': {
                'subject': _('Application shortlisted: %s') % position,
                'body': _('<p>Dear %s,</p><p>We are pleased to let you know that your application for '
                          '<strong>%s</strong> has been shortlisted for the qualification stage.</p>'
                          '<p>We will share the next steps shortly.</p><p>Regards,<br/>HR Team</p>') %
                        (applicant, position),
            },
            'first_interview': {
                'subject': _('First interview invitation: %s') % position,
                'body': _('<p>Dear %s,</p><p>You have been shortlisted for the first interview for '
                          '<strong>%s</strong>.</p><p>Please attend at the date and time shown below.</p>'
                          '<p>Regards,<br/>HR Team</p>') % (applicant, position),
            },
            'second_interview': {
                'subject': _('Second interview invitation: %s') % position,
                'body': _('<p>Dear %s,</p><p>You are invited to the second interview for '
                          '<strong>%s</strong>.</p><p>Please attend at the date and time shown below.</p>'
                          '<p>Regards,<br/>HR Team</p>') % (applicant, position),
            },
            'selection': {
                'subject': _('You have been selected: %s') % position,
                'body': _('<p>Dear %s,</p><p>Congratulations. You have been selected for the position of '
                          '<strong>%s</strong>.</p><p>Please confirm that you are interested by selecting '
                          '<a href="%s">I am interested</a>.</p><p>Regards,<br/>HR Team</p>') %
                        (applicant, position, self._interest_url(application)),
            },
            'offer': {
                'subject': _('Offer letter: %s') % position,
                'body': _('<p>Dear %s,</p><p>We are pleased to share an offer for the position of '
                          '<strong>%s</strong>.</p><p>Please review the offer details and contact HR for '
                          'any clarification.</p><p>Regards,<br/>HR Team</p>') % (applicant, position),
            },
        }
        return contents[email_type]

    @api.onchange('interview_date', 'interview_time')
    def _onchange_interview_schedule(self):
        for wizard in self:
            if wizard.email_type not in ('first_interview', 'second_interview'):
                continue
            content = wizard._email_content(wizard.application_id, wizard.email_type)
            schedule = ''
            if wizard.interview_date:
                schedule = fields.Date.to_string(wizard.interview_date)
            if wizard.interview_time is not False:
                hours = int(wizard.interview_time)
                minutes = round((wizard.interview_time - hours) * 60)
                schedule = '%s at %02d:%02d' % (schedule, hours, minutes)
            if schedule:
                content['body'] = content['body'].replace(
                    '</p><p>Regards,', '</p><p><strong>Interview schedule:</strong> %s</p><p>Regards,' % schedule)
            wizard.subject = content['subject']
            wizard.body = content['body']

    def action_send_email(self):
        self.ensure_one()
        if not self.email_to:
            raise UserError(_('Enter the applicant email address before sending.'))
        if self.email_type in ('first_interview', 'second_interview'):
            if not self.interview_date or self.interview_time is False:
                raise ValidationError(_('Enter both interview date and interview time.'))
        mail = self.env['mail.mail'].create({
            'subject': self.subject,
            'body_html': self.body,
            'email_to': self.email_to,
            'email_from': self.env.user.email_formatted or self.env.company.email,
            'model': 'manpower.application',
            'res_id': self.application_id.id,
        })
        mail.send()
        self.application_id.message_post(body=_('Stage email sent: %s') % self.subject)
        return {'type': 'ir.actions.act_window_close'}
