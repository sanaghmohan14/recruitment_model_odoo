from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class ManpowerApplicationRejectWizard(models.TransientModel):
    _name = 'manpower.application.reject.wizard'
    _description = 'Reject Manpower Application'

    application_id = fields.Many2one(
        'manpower.application', string='Application', required=True, readonly=True)
    reject_reason = fields.Text(string='Rejection Reason', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        application = self.application_id.exists()
        if not application or application.stage not in ('first_interview', 'second_interview'):
            raise UserError(_('This application can no longer be rejected.'))
        if not self.reject_reason or not self.reject_reason.strip():
            raise ValidationError(_('Enter a rejection reason before rejecting the application.'))
        application.write({
            'stage': 'cancelled',
            'reject_reason': self.reject_reason.strip(),
        })
        application.message_post(body=_('Application rejected. Reason: %s') % self.reject_reason.strip())
        return {'type': 'ir.actions.act_window_close'}
