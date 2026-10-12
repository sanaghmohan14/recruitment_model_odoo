from odoo import http
from odoo.http import request


class ManpowerApplicationInterestController(http.Controller):

    @http.route('/manpower/application/<int:application_id>/interest/<string:token>',
                type='http', auth='public', methods=['GET'], csrf=False)
    def confirm_interest(self, application_id, token, **kwargs):
        application = request.env['manpower.application'].sudo().browse(application_id).exists()
        if not application or application.interest_token != token:
            return request.not_found()
        if application.stage == 'contract_proposal':
            application.write({
                'candidate_interest': 'interested',
                'stage': 'contract_signed',
            })
        return request.make_response(
            '<html><body><h2>Thank you</h2><p>Your interest has been confirmed. '
            'Our HR team will contact you shortly.</p></body></html>',
            headers=[('Content-Type', 'text/html; charset=utf-8')],
        )
