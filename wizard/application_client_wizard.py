from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ManpowerApplicationClientWizard(models.TransientModel):
    _name = 'manpower.application.client.wizard'
    _description = 'Send Candidate Update to Client'

    application_id = fields.Many2one('manpower.application', string='Application', required=True, readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    email_to = fields.Char(string='Recipient Email', required=True)
    stage_label = fields.Char(string='Current Stage', readonly=True)
    subject = fields.Char(string='Subject', required=True)
    body = fields.Html(string='Message', required=True, sanitize_style=True)

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        application_id = self.env.context.get('default_application_id')
        application = self.env['manpower.application'].browse(application_id).exists()
        if application:
            client = (
                application.client_id
                or (application.job_opening_id and application.job_opening_id.client_id)
                or (application.job_opening_id and application.job_opening_id.requirement_id and application.job_opening_id.requirement_id.client_id)
            )
            values['application_id'] = application.id
            values['client_id'] = client.id if client else False
            values['email_to'] = client.email if client else ''

            stage_dict = dict(application._fields['stage'].selection)
            stage_label = stage_dict.get(application.stage, application.stage)
            values['stage_label'] = stage_label

            pos_title = application.job_opening_id.title or _('Position')
            subject = _("Candidate Application Update: %(cand)s for %(pos)s - %(stage)s") % {
                'cand': application.applicant_name or _('Candidate'),
                'pos': pos_title,
                'stage': stage_label,
            }
            values['subject'] = subject
            values['body'] = self._build_email_body(application, client, stage_label)
        return values

    def _build_email_body(self, application, client, stage_label):
        client_name = client.name if client else _('Client')
        company = application.company_id or self.env.company
        cand_name = application.applicant_name or ''
        pos = application.job_opening_id.title or ''
        ref = application.name or ''

        details = [
            (_('Candidate Name'), f'<strong>{cand_name}</strong>'),
            (_('Position / Opening'), pos),
            (_('Application Reference'), ref),
            (_('Current Stage'), f'<strong style="color: #0d6efd;">{stage_label}</strong>'),
        ]

        if application.total_experience:
            details.append((_('Total Experience'), f"{application.total_experience} " + _("years")))
        if application.current_designation or application.current_employer:
            curr = f"{application.current_designation or ''}"
            if application.current_employer:
                curr += f" at {application.current_employer}" if curr else application.current_employer
            details.append((_('Current Role'), curr))
        if application.highest_qualification:
            qual = application.highest_qualification
            if application.specialization:
                qual += f" ({application.specialization})"
            details.append((_('Highest Qualification'), qual))
        if application.notice_period:
            details.append((_('Notice Period'), application.notice_period))

        score_dict = dict(application._fields['first_interview_score'].selection or [])
        if application.first_interview_score and application.first_interview_score != '0':
            details.append((_('Internal Interview Rating'), score_dict.get(application.first_interview_score, application.first_interview_score)))
        if application.second_interview_score and application.second_interview_score != '0':
            details.append((_('Manager Interview Rating'), score_dict.get(application.second_interview_score, application.second_interview_score)))
        if application.third_interview_score and application.third_interview_score != '0':
            details.append((_('Client Interview Rating'), score_dict.get(application.third_interview_score, application.third_interview_score)))

        rows_html = ""
        for i, (label, val) in enumerate(details):
            bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"
            rows_html += (
                f'<tr style="background-color: {bg}; border-bottom: 1px solid #e0e0e0;">'
                f'<td style="padding: 9px 14px; font-weight: 600; color: #495057; width: 35%;">{label}</td>'
                f'<td style="padding: 9px 14px; color: #212529;">{val}</td>'
                f'</tr>'
            )

        html = f"""
        <p>Dear {client_name},</p>
        <p>We are pleased to provide an update on candidate <strong>{cand_name}</strong> for the position of <strong>{pos}</strong>.</p>
        <table style="width: 100%; max-width: 650px; border-collapse: collapse; margin: 18px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; border: 1px solid #dee2e6; border-radius: 6px; overflow: hidden;">
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <p>Please review the details above and let us know if you require any additional information or have feedback on this candidate.</p>
        <p>Warm regards,<br/><strong>{company.name}</strong></p>
        """
        return html

    def action_send_email(self):
        self.ensure_one()
        if not self.email_to:
            raise UserError(_('Please enter a recipient email address.'))

        mail = self.env['mail.mail'].create({
            'subject': self.subject,
            'body_html': self.body,
            'email_to': self.email_to,
            'email_from': self.env.user.email_formatted or self.env.company.email,
            'model': 'manpower.application',
            'res_id': self.application_id.id,
        })
        mail.send()

        self.application_id.message_post(
            body=_("Client update email sent to <strong>%(client)s</strong> &lt;%(email)s&gt; for stage: <strong>%(stage)s</strong>.<br/>Subject: %(sub)s") % {
                'client': self.client_id.name,
                'email': self.email_to,
                'stage': self.stage_label,
                'sub': self.subject,
            },
            subtype_xmlid='mail.mt_comment',
        )
        return {'type': 'ir.actions.act_window_close'}
