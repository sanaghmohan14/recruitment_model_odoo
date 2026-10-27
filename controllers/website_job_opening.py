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
        return request.render('manpower_requisition.manpower_job_opening_detail', {
            'job': job,
            'post': {},
        })

    @http.route('/manpower/jobs/<int:job_id>/apply', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def apply(self, job_id, **post):
        job = request.env['manpower.job.opening'].sudo().browse(job_id).exists()
        if not job or job.state != 'published':
            return request.not_found()
        if job.is_expired:
            return request.render('manpower_requisition.manpower_job_opening_detail', {
                'job': job,
                'error': 'This job opening has expired and is no longer accepting applications.',
                'post': post,
            })

        applicant_name = (post.get('applicant_name') or '').strip()
        email = (post.get('email') or '').strip()
        mobile = (post.get('mobile') or post.get('phone') or '').strip()
        phone = (post.get('phone') or mobile).strip()

        if not applicant_name or not email or not mobile:
            return request.render('manpower_requisition.manpower_job_opening_detail', {
                'job': job,
                'error': 'Please enter your Name, Email, and Mobile number.',
                'post': post,
            })

        def parse_float(val):
            if not val:
                return 0.0
            try:
                return float(str(val).replace(',', '').strip())
            except (ValueError, TypeError):
                return 0.0

        dob = post.get('date_of_birth') or False
        gender = post.get('gender')
        if gender not in ('male', 'female', 'other'):
            gender = False

        app_vals = {
            'applicant_name': applicant_name,
            'email': email,
            'mobile': mobile,
            'phone': phone,
            'job_opening_id': job.id,
            'date_of_birth': dob,
            'gender': gender,
            'address': (post.get('address') or '').strip() or False,
            'highest_qualification': (post.get('highest_qualification') or '').strip() or False,
            'specialization': (post.get('specialization') or '').strip() or False,
            'institution': (post.get('institution') or '').strip() or False,
            'graduation_year': (post.get('graduation_year') or '').strip() or False,
            'total_experience': parse_float(post.get('total_experience')),
            'current_employer': (post.get('current_employer') or '').strip() or False,
            'current_designation': (post.get('current_designation') or '').strip() or False,
            'experience_details': (post.get('experience_details') or '').strip() or False,
            'current_salary': parse_float(post.get('current_salary')),
            'expected_salary': parse_float(post.get('expected_salary')),
            'notice_period': (post.get('notice_period') or '').strip() or False,
        }

        request.env['manpower.application'].sudo().create(app_vals)
        return request.render('manpower_requisition.manpower_job_application_thanks', {'job': job})

