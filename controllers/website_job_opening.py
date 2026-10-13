from odoo import http
from odoo.http import request


class ManpowerWebsiteJobOpeningController(http.Controller):

    @http.route('/manpower/jobs', type='http', auth='public', website=True)
    def job_list(self, **kwargs):
        jobs = request.env['manpower.job.opening'].sudo().search(
            [('state', '=', 'published')], order='posting_date desc, id desc')
        return request.render('manpower_requisition.manpower_job_opening_list', {'jobs': jobs})

    @http.route('/manpower/jobs/<int:job_id>', type='http', auth='public', website=True)
    def job_detail(self, job_id, **kwargs):
        job = request.env['manpower.job.opening'].sudo().browse(job_id).exists()
        if not job or job.state != 'published':
            return request.not_found()
        return request.render('manpower_requisition.manpower_job_opening_detail', {'job': job})

    @http.route('/manpower/jobs/<int:job_id>/apply', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def apply(self, job_id, **post):
        job = request.env['manpower.job.opening'].sudo().browse(job_id).exists()
        if not job or job.state != 'published':
            return request.not_found()
        applicant_name = (post.get('applicant_name') or '').strip()
        email = (post.get('email') or '').strip()
        if not applicant_name or not email:
            return request.render('manpower_requisition.manpower_job_opening_detail', {
                'job': job,
                'error': 'Please enter your name and email address.',
            })
        request.env['manpower.application'].sudo().create({
            'applicant_name': applicant_name,
            'email': email,
            'phone': (post.get('phone') or '').strip(),
            'job_opening_id': job.id,
        })
        return request.render('manpower_requisition.manpower_job_application_thanks', {'job': job})
