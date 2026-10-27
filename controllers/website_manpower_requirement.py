from datetime import date
from odoo import _, fields, http
from odoo.http import request

GROUP_PROJECT_MANAGER = 'manpower_requisition.group_project_manager'


class WebsiteManpowerRequirementController(http.Controller):

    def _get_available_job_roles(self):
        tasks = request.env['project.task'].sudo().search([('active', '=', True)], order='name asc')
        openings = request.env['manpower.job.opening'].sudo().search([('state', '=', 'published')], order='title asc')
        role_set = {t.name.strip() for t in tasks if t.name and t.name.strip()}
        role_set.update({o.title.strip() for o in openings if o.title and o.title.strip()})
        return sorted(list(role_set))

    @http.route([
        '/manpower/requirement',
        '/manpower/submit-requirement',
        '/hire-talent',
    ], type='http', auth='public', website=True, methods=['GET'])
    def requirement_form(self, **kwargs):
        skills = request.env['manpower.skill'].sudo().search([('active', '=', True)], order='name asc')
        job_roles = self._get_available_job_roles()
        partners = request.env['res.partner'].sudo().search([('type', '!=', 'private')], order='name asc')
        post_data = dict(kwargs)
        if kwargs.get('role') and not post_data.get('job_title'):
            post_data['job_title'] = kwargs['role']
        if kwargs.get('job_role') and not post_data.get('job_title'):
            post_data['job_title'] = kwargs['job_role']
        return request.render('manpower_requisition.manpower_client_requirement_form', {
            'skills': skills,
            'job_roles': job_roles,
            'partners': partners,
            'post': post_data,
            'error': None,
        })

    @http.route('/manpower/requirement/submit', type='http', auth='public', website=True,
                methods=['POST'], csrf=True)
    def requirement_submit(self, **post):
        # 1. Extract and sanitize inputs
        client_id_val = post.get('client_id') or post.get('partner_id')
        partner = False
        if client_id_val:
            try:
                partner = request.env['res.partner'].sudo().browse(int(client_id_val)).exists()
            except (ValueError, TypeError):
                partner = False

        client_contact_name = (post.get('client_contact_name') or post.get('name') or (partner.name if partner else '')).strip()
        client_company_name = (
            partner.parent_id.name if partner and partner.parent_id
            else (partner.name if partner and partner.is_company else (post.get('client_company_name') or post.get('company_name') or ''))
        ).strip()
        client_email = (post.get('client_email') or post.get('email') or (partner.email if partner else '')).strip()
        client_phone = (post.get('client_phone') or post.get('contact_no') or post.get('phone') or (partner.phone if partner else '')).strip()
        job_title = (post.get('job_title') or post.get('job_role') or '').strip()
        qualification = (post.get('qualification') or '').strip()
        location = (post.get('location') or post.get('job_location') or '').strip()
        closing_date_str = (post.get('closing_date') or '').strip()
        joining_requirement = post.get('joining_requirement') or 'immediate'
        joining_date_str = (post.get('joining_date') or '').strip()
        reason = post.get('reason') or 'project'
        job_description = (post.get('job_description') or post.get('description') or '').strip()

        skills = request.env['manpower.skill'].sudo().search([('active', '=', True)], order='name asc')
        partners = request.env['res.partner'].sudo().search([('type', '!=', 'private')], order='name asc')

        def render_with_error(error_msg):
            return request.render('manpower_requisition.manpower_client_requirement_form', {
                'skills': skills,
                'job_roles': self._get_available_job_roles(),
                'partners': partners,
                'post': post,
                'error': error_msg,
            })

        # 2. Validation
        if not partner and not client_contact_name:
            return render_with_error(_('Please select a partner / name.'))
        if not client_email:
            return render_with_error(_('Please enter your email address.'))
        if not client_phone:
            return render_with_error(_('Please enter your contact number.'))
        if not job_title:
            return render_with_error(_('Please enter the job role / position title.'))
        if not location:
            return render_with_error(_('Please enter the preferred job location.'))

        def parse_float(val):
            if not val:
                return 0.0
            try:
                return float(str(val).replace(',', '').strip())
            except (ValueError, TypeError):
                return 0.0

        def parse_int(val, default=1):
            if not val:
                return default
            try:
                res = int(str(val).strip())
                return res if res >= 1 else default
            except (ValueError, TypeError):
                return default

        vacancies = parse_int(post.get('vacancies'), default=1)
        experience_min = parse_float(post.get('experience_min') or post.get('years_of_experience'))
        experience_max = parse_float(post.get('experience_max'))
        if experience_max and experience_min and experience_max < experience_min:
            return render_with_error(_('Maximum experience cannot be less than minimum experience.'))

        salary_min = parse_float(post.get('salary_min'))
        salary_max = parse_float(post.get('salary_max'))
        if salary_max and salary_min and salary_max < salary_min:
            return render_with_error(_('Maximum salary cannot be less than minimum salary.'))

        closing_date = False
        if closing_date_str:
            try:
                closing_date = fields.Date.from_string(closing_date_str)
                if closing_date < date.today():
                    return render_with_error(_('Closing date cannot be in the past.'))
            except Exception:
                return render_with_error(_('Invalid closing date format.'))

        joining_date = False
        if joining_date_str:
            try:
                joining_date = fields.Date.from_string(joining_date_str)
            except Exception:
                joining_date = False

        # 3. Match or Create Partner (if not selected)
        if not partner:
            Partner = request.env['res.partner'].sudo()
            partner = Partner.search([('email', '=ilike', client_email)], limit=1)
            if not partner and client_company_name:
                partner = Partner.search([('is_company', '=', True), ('name', '=ilike', client_company_name)], limit=1)

            if not partner:
                if client_company_name:
                    company_partner = Partner.create({
                        'name': client_company_name,
                        'is_company': True,
                        'email': client_email,
                        'phone': client_phone,
                        'city': location or False,
                    })
                    if client_contact_name and client_contact_name.lower() != client_company_name.lower():
                        partner = Partner.create({
                            'name': client_contact_name,
                            'parent_id': company_partner.id,
                            'email': client_email,
                            'phone': client_phone,
                            'type': 'contact',
                        })
                    else:
                        partner = company_partner
                else:
                    partner = Partner.create({
                        'name': client_contact_name,
                        'email': client_email,
                        'phone': client_phone,
                        'city': location or False,
                        'is_company': False,
                    })

        # 4. Handle Skills
        skill_ids = []
        selected_skills = request.httprequest.form.getlist('skill_ids')
        for sid in selected_skills:
            try:
                skill_ids.append(int(sid))
            except (ValueError, TypeError):
                pass

        custom_skills_raw = (post.get('custom_skills') or '').strip()
        if custom_skills_raw:
            Skill = request.env['manpower.skill'].sudo()
            for sname in [s.strip() for s in custom_skills_raw.split(',') if s.strip()]:
                skill = Skill.search([('name', '=ilike', sname)], limit=1)
                if not skill:
                    skill = Skill.create({'name': sname})
                if skill.id not in skill_ids:
                    skill_ids.append(skill.id)

        # 5. Automatically locate or create the Project and Job Role (Task)
        Project = request.env['project.project'].sudo()
        Task = request.env['project.task'].sudo()

        project = Project.search([('hiring_required', '=', True)], limit=1)
        if not project:
            project = Project.search([('name', '=ilike', 'Hiring%')], limit=1)
        if not project:
            project = Project.create({
                'name': 'Hiring & Recruitment',
                'hiring_required': True,
            })

        task = Task.search([
            ('project_id', '=', project.id),
            ('name', '=ilike', job_title),
        ], limit=1)
        if not task:
            task = Task.create({
                'name': job_title,
                'project_id': project.id,
                'partner_id': partner.id if partner else False,
                'client_id': partner.id if partner else False,
                'hiring_required': True,
                'hiring_submitted': True,
            })

        # 6. Create Requirement
        vals = {
            'request_type': 'client',
            'client_id': partner.id if partner else False,
            'client_contact_name': client_contact_name,
            'client_company_name': client_company_name,
            'client_email': client_email,
            'client_phone': client_phone,
            'client_address': location or (partner.contact_address if partner else ''),
            'project_id': project.id,
            'task_id': task.id,
            'job_title': job_title,
            'qualification': qualification,
            'location': location,
            'vacancies': vacancies,
            'experience_min': experience_min,
            'experience_max': experience_max,
            'salary_min': salary_min,
            'salary_max': salary_max,
            'closing_date': closing_date,
            'joining_requirement': joining_requirement if joining_requirement in ('immediate', '15', '30', '60', '90', 'other') else 'immediate',
            'joining_date': joining_date,
            'reason': reason if reason in ('new_position', 'replacement', 'expansion', 'project', 'other') else 'project',
            'job_description': job_description,
            'state': 'draft',
        }
        if skill_ids:
            vals['skill_ids'] = [(6, 0, skill_ids)]

        requirement = request.env['manpower.requirement'].sudo().create(vals)

        # 6. Post chatter note and notify PM
        closing_display = closing_date.strftime('%d-%b-%Y') if closing_date else _('Not specified')
        salary_display = _('Not specified')
        if salary_min and salary_max:
            salary_display = f"{salary_min:,.0f} - {salary_max:,.0f}"
        elif salary_min:
            salary_display = f"From {salary_min:,.0f}"
        elif salary_max:
            salary_display = f"Up to {salary_max:,.0f}"

        body = _(
            "<strong>New Manpower Requirement submitted via Website</strong><br/>"
            "<ul>"
            "<li><strong>Client Contact:</strong> %(contact)s</li>"
            "<li><strong>Company:</strong> %(company)s</li>"
            "<li><strong>Email:</strong> %(email)s | <strong>Phone:</strong> %(phone)s</li>"
            "<li><strong>Job Role:</strong> %(role)s (%(vacancies)s vacancy/ies)</li>"
            "<li><strong>Location:</strong> %(location)s</li>"
            "<li><strong>Qualification:</strong> %(qual)s</li>"
            "<li><strong>Experience:</strong> %(exp_min)s - %(exp_max)s years</li>"
            "<li><strong>Salary Range:</strong> %(salary)s</li>"
            "<li><strong>Target Closing Date:</strong> %(closing)s</li>"
            "</ul>"
        ) % {
            'contact': partner.display_name if partner else client_contact_name,
            'company': client_company_name or 'N/A',
            'email': client_email,
            'phone': client_phone,
            'role': job_title,
            'vacancies': vacancies,
            'location': location,
            'qual': qualification or 'N/A',
            'exp_min': experience_min,
            'exp_max': experience_max,
            'salary': salary_display,
            'closing': closing_display,
        }
        requirement.message_post(body=body, subtype_xmlid='mail.mt_comment')

        client_display = partner.display_name if partner else (client_company_name or client_contact_name)
        requirement._notify_group(
            GROUP_PROJECT_MANAGER,
            _("A new manpower requisition (%(ref)s) has been submitted via website by %(company)s for '%(role)s'.") % {
                'ref': requirement.name,
                'company': client_display,
                'role': job_title,
            }
        )

        return request.redirect('/manpower/requirement/thank-you/%s' % requirement.id)

    @http.route('/manpower/requirement/thank-you/<int:requirement_id>', type='http', auth='public', website=True)
    def requirement_thanks(self, requirement_id, **kwargs):
        requirement = request.env['manpower.requirement'].sudo().browse(requirement_id).exists()
        if not requirement:
            return request.redirect('/manpower/requirement')
        return request.render('manpower_requisition.manpower_client_requirement_thanks', {
            'requirement': requirement,
        })
