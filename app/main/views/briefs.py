# coding: utf-8
from __future__ import unicode_literals

import re

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from dmapiclient import HTTPError

from ..helpers import login_required
from ..helpers.briefs import (
    get_brief,
    is_supplier_eligible_for_brief,
    send_brief_clarification_question,
    supplier_has_a_brief_response
)
from ..helpers.frameworks import get_framework_and_lot
from ...main import main, content_loader
from ... import data_api_client


@main.route('/opportunities/<int:brief_id>/question-and-answer-session', methods=['GET'])
@login_required
def question_and_answer_session(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if brief['clarificationQuestionsAreClosed']:
        abort(404)

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief, clarification_question=True)

    return render_template(
        "briefs/question_and_answer_session.html",
        brief=brief,
    ), 200


@main.route('/opportunities/<int:brief_id>/ask-a-question', methods=['GET', 'POST'])
@login_required
def ask_brief_clarification_question(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if brief['clarificationQuestionsAreClosed']:
        abort(404)

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief, clarification_question=True)

    error_message = None
    clarification_question_value = None

    if request.method == 'POST':
        clarification_question = request.form.get('clarification-question', '').strip()
        if not clarification_question:
            error_message = "Question cannot be empty"
        elif len(clarification_question) > 5000:
            clarification_question_value = clarification_question
            error_message = "Question cannot be longer than 5000 characters"
        elif not re.match("^$|(^(?:\\S+\\s+){0,99}\\S+$)", clarification_question):
            clarification_question_value = clarification_question
            error_message = "Question must be no more than 100 words"
        else:
            send_brief_clarification_question(data_api_client, brief, clarification_question)
            flash('message_sent', 'success')

    return render_template(
        "briefs/clarification_question.html",
        brief=brief,
        error_message=error_message,
        clarification_question_name='clarification-question',
        clarification_question_value=clarification_question_value
    ), 200 if not error_message else 400


@main.route('/opportunities/<int:brief_id>/responses/start', methods=['GET', 'POST'])
@login_required
def start_brief_response(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    if request.method == 'POST':
        brief_response = data_api_client.create_brief_response(
            brief_id,
            current_user.supplier_id,
            {},
            current_user.email_address,
        )['briefResponses']
        brief_response_id = brief_response['id']
        return redirect(url_for('.edit_brief_response', brief_response_id=brief_response_id))

    brief_response = data_api_client.find_brief_responses(
        brief_id=brief_id,
        supplier_id=current_user.supplier_id,
        status='draft,submitted'
    )['briefResponses']

    if brief_response:
        if brief_response[0].get('status') == 'submitted':
            flash('already_applied', 'error')
            return redirect(url_for(".view_response_result", brief_id=brief_id))
        if brief_response[0].get('status') == 'draft':
            existing_draft_response = True
    else:
        existing_draft_response = False

    return render_template(
        "briefs/start_brief_response.html",
        brief=brief,
        existing_draft_response=existing_draft_response
    )


@main.route('/opportunities/responses/<int:brief_response_id>/edit', methods=['GET'])
@login_required
def edit_brief_response(brief_response_id):
    return 'Hello world'


@main.route('/opportunities/<int:brief_id>/responses/create', methods=['GET'])
@login_required
def brief_response(brief_id):

    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    if supplier_has_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
        flash('already_applied', 'error')
        return redirect(url_for(".view_response_result", brief_id=brief_id))

    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live'])

    content = content_loader.get_manifest(framework['slug'], 'edit_brief_response').filter({'lot': lot['slug']})
    section = content.get_section(content.get_next_editable_section_id())

    # replace generic 'Apply for opportunity' title with title including the name of the brief
    section.name = "Apply for ‘{}’".format(brief['title'])
    section.inject_brief_questions_into_boolean_list_question(brief)

    return render_template(
        "briefs/brief_response.html",
        brief=brief,
        service_data={},
        section=section,
        **dict(main.config['BASE_TEMPLATE_DATA'])
    ), 200


# Add a create route
@main.route('/opportunities/<int:brief_id>/responses/create', methods=['POST'])
@login_required
def create_brief_response(brief_id):
    """Hits up the data API to create a new brief response."""

    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live'])

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    if supplier_has_a_brief_response(data_api_client, current_user.supplier_id, brief_id):
        flash('already_applied', 'error')
        return redirect(url_for(".view_response_result", brief_id=brief_id))

    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live'])

    content = content_loader.get_manifest(framework['slug'], 'edit_brief_response').filter({'lot': lot['slug']})
    section = content.get_section(content.get_next_editable_section_id())
    response_data = section.get_data(request.form)

    try:
        brief_response = data_api_client.create_brief_response(
            brief_id,
            current_user.supplier_id,
            response_data,
            current_user.email_address,
            page_questions=section.get_field_names()
        )['briefResponses']
        data_api_client.submit_brief_response(brief_response['id'], current_user.email_address)

    except HTTPError as e:
        # replace generic 'Apply for opportunity' title with title including the name of the brief
        section.name = "Apply for ‘{}’".format(brief['title'])
        section.inject_brief_questions_into_boolean_list_question(brief)
        section_summary = section.summary(response_data)

        errors = section_summary.get_error_messages(e.message)

        return render_template(
            "briefs/brief_response.html",
            brief=brief,
            service_data=response_data,
            section=section,
            errors=errors,
            **dict(main.config['BASE_TEMPLATE_DATA'])
        ), 400

    if all(brief_response['essentialRequirements']):
        # "result" parameter is used to track brief applications by analytics
        return redirect(url_for(".view_response_result", brief_id=brief_id, result='success'))
    else:
        return redirect(url_for(".view_response_result", brief_id=brief_id, result='fail'))


@main.route('/opportunities/<int:brief_id>/responses/result')
@login_required
def view_response_result(brief_id):
    brief = get_brief(data_api_client, brief_id, allowed_statuses=['live', 'closed'])

    if not is_supplier_eligible_for_brief(data_api_client, current_user.supplier_id, brief):
        return _render_not_eligible_for_brief_error_page(brief)

    brief_response = data_api_client.find_brief_responses(
        brief_id=brief_id,
        supplier_id=current_user.supplier_id
    )['briefResponses']

    if len(brief_response) == 0:
        return redirect(url_for(".brief_response", brief_id=brief_id))
    elif all(brief_response[0]['essentialRequirements']):
        result_state = 'submitted_ok'
    else:
        result_state = 'submitted_unsuccessful'

    brief_response = brief_response[0]
    framework, lot = get_framework_and_lot(
        data_api_client, brief['frameworkSlug'], brief['lotSlug'], allowed_statuses=['live'])

    response_content = content_loader.get_manifest(
        framework['slug'], 'display_brief_response').filter({'lot': lot['slug']})
    for section in response_content:
        section.inject_brief_questions_into_boolean_list_question(brief)

    brief_content = content_loader.get_manifest(
        framework['slug'], 'edit_brief').filter({'lot': lot['slug']})
    brief_summary = brief_content.summary(brief)

    return render_template(
        'briefs/view_response_result.html',
        brief=brief,
        brief_summary=brief_summary,
        brief_response=brief_response,
        result_state=result_state,
        response_content=response_content
    )


def _render_not_eligible_for_brief_error_page(brief, clarification_question=False):
    common_kwargs = {
        "supplier_id": current_user.supplier_id,
        "framework": brief['frameworkSlug'],
        "status": "published",
    }

    if data_api_client.find_services(**common_kwargs)["services"]:
        if data_api_client.find_services(**dict(common_kwargs, lot=brief["lotSlug"]))["services"]:
            # deduce that the problem is that the roles don't match.
            reason = data_reason_slug = "supplier-not-on-role"
        else:
            reason = data_reason_slug = "supplier-not-on-lot"
    else:
        reason = "supplier-not-on-framework"
        data_reason_slug = "supplier-not-on-{}".format(brief['frameworkFramework'])

    return render_template(
        "briefs/not_is_supplier_eligible_for_brief_error.html",
        clarification_question=clarification_question,
        framework_name=brief['frameworkName'],
        lot=brief['lotSlug'],
        reason=reason,
        data_reason_slug=data_reason_slug,
        **dict(main.config['BASE_TEMPLATE_DATA'])
    ), 400
