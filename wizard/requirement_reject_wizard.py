from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


GROUP_HR = 'manpower_requisition.group_hr'
GROUP_CEO = 'manpower_requisition.group_ceo'


class ManpowerRequirementRejectWizard(models.TransientModel):
    _name = 'manpower.requirement.reject.wizard'
    _description = 'Reject Manpower Requirement'

    requirement_id = fields.Many2one(
        'manpower.requirement', string='Manpower Requirement', required=True, readonly=True)
    reject_reason = fields.Text(string='Rejection Details', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        requirement = self.requirement_id.exists()
        if not requirement:
            raise UserError(_('The manpower requirement no longer exists.'))
        if requirement.state == 'hr_review':
            requirement._check_group(GROUP_HR)
        elif requirement.state == 'pending_approval':
            requirement._check_group(GROUP_CEO)
        else:
            raise UserError(_('This requirement can no longer be rejected.'))
        if not self.reject_reason or not self.reject_reason.strip():
            raise ValidationError(_('Enter rejection details before rejecting the requirement.'))
        requirement.write({
            'state': 'rejected',
            'reject_reason': self.reject_reason.strip(),
        })
        requirement.message_post(
            body=_('Manpower requirement rejected. Details: %s') % self.reject_reason.strip())
        return {'type': 'ir.actions.act_window_close'}
