from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ManpowerRequirementClientWizard(models.TransientModel):
    _name = 'manpower.requirement.client.wizard'
    _description = 'Send Requirement Update to Client'

    requirement_id = fields.Many2one('manpower.requirement', string='Requirement', required=True, readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True)
    email_to = fields.Char(string='Recipient Email', required=True)
    stage_label = fields.Char(string='Current Stage', readonly=True)
    subject = fields.Char(string='Subject', required=True)
    body = fields.Html(string='Message', required=True, sanitize_style=True)

    @api.model
    def default_get(self, field_list):
        values = super().default_get(field_list)
        requirement_id = self.env.context.get('default_requirement_id')
        requirement = self.env['manpower.requirement'].browse(requirement_id).exists()
        if requirement:
            client = requirement.client_id
            values['requirement_id'] = requirement.id
            values['client_id'] = client.id if client else False
            values['email_to'] = client.email if client else ''

            stage_dict = dict(requirement._fields['state'].selection)
            stage_label = stage_dict.get(requirement.state, requirement.state)
            values['stage_label'] = stage_label

            subject = _("Update on Manpower Requisition: %(pos)s (%(ref)s) - %(stage)s") % {
                'pos': requirement.job_title or _('Position'),
                'ref': requirement.name,
                'stage': stage_label,
            }
            values['subject'] = subject
            values['body'] = self._build_email_body(requirement, client, stage_label)
        return values

    def _build_email_body(self, requirement, client, stage_label):
        client_name = client.name if client else _('Client')
        company = requirement.company_id or self.env.company
        pos = requirement.job_title or ''
        ref = requirement.name or ''
        vacancies = requirement.vacancies or 1

        details = [
            (_('Requisition Reference'), ref),
            (_('Job Position'), pos),
            (_('Current Stage'), f'<strong style="color: #0d6efd;">{stage_label}</strong>'),
            (_('Number of Vacancies'), str(vacancies)),
        ]

        if requirement.project_id:
            details.append((_('Project'), requirement.project_id.name))
        if requirement.task_id:
            details.append((_('Job Role / Task'), requirement.task_id.name))
        if requirement.experience_min or requirement.experience_max:
            exp_text = f"{requirement.experience_min or 0} - {requirement.experience_max or 0} " + _("years")
            details.append((_('Required Experience'), exp_text))
        if requirement.qualification:
            details.append((_('Qualification'), requirement.qualification))
        if requirement.skill_ids:
            skills = ", ".join(requirement.skill_ids.mapped('name'))
            details.append((_('Skills Required'), skills))
        if requirement.location:
            details.append((_('Location'), requirement.location))
        if requirement.joining_requirement:
            joining_dict = dict(requirement._fields['joining_requirement'].selection or [])
            joining_text = joining_dict.get(requirement.joining_requirement, requirement.joining_requirement)
            if requirement.joining_date:
                joining_text += f" ({requirement.joining_date})"
            details.append((_('Expected Joining'), joining_text))
        if requirement.pm_notes and requirement.state in ('pm_review', 'hr_review', 'pending_approval', 'approved'):
            details.append((_('Project Manager Notes'), requirement.pm_notes))
        if requirement.hr_notes and requirement.state in ('hr_review', 'pending_approval', 'approved'):
            details.append((_('HR Notes'), requirement.hr_notes))

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
        <p>We are pleased to provide you with the latest update regarding your manpower requisition for <strong>{pos}</strong>.</p>
        <table style="width: 100%; max-width: 650px; border-collapse: collapse; margin: 18px 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; font-size: 14px; border: 1px solid #dee2e6; border-radius: 6px; overflow: hidden;">
            <tbody>
                {rows_html}
            </tbody>
        </table>
        <p>We are actively progressing with the fulfillment of this requirement and will keep you posted on the next milestones.</p>
        <p>Should you have any questions or feedback, please feel free to reach out.</p>
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
            'model': 'manpower.requirement',
            'res_id': self.requirement_id.id,
        })
        mail.send()

        self.requirement_id.message_post(
            body=_("Client update email sent to <strong>%(client)s</strong> &lt;%(email)s&gt; for stage: <strong>%(stage)s</strong>.<br/>Subject: %(sub)s") % {
                'client': self.client_id.name,
                'email': self.email_to,
                'stage': self.stage_label,
                'sub': self.subject,
            },
            subtype_xmlid='mail.mt_comment',
        )
        return {'type': 'ir.actions.act_window_close'}
