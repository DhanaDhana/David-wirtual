from .models import DraftCheckList, ClientCheckList, CategorySummary, CategoryAndSubCategory, ClientTask, ExtractedData
from data_collection.models import SurveyFormData
from clients.models import InstrumentsRecomended, Staff, ClientInstrumentInfo, Client, Document
from django.db.models import F, Count
from decimal import Decimal

def draftupdate_check(client, checklistid):
    result = 'failed'
    recommended_fundrisknames = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,is_active=True).values_list('fund_risk__fund_name',flat=True)
    recommended_reasons = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,
                                                               function_list__function_type='1',
                                                               is_active=True).values_list('reason', flat=True)
    if checklistid == 19:
        result = 'amber' if '11' in recommended_fundrisknames else 'passed'  # other in aleast one instrument
    elif checklistid in [20, 21]:
        result = 'amber'
    elif checklistid == 23:
        result = 'passed' if None not in recommended_reasons else 'failed'
    elif checklistid == 49:
        dataextraction_docs = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,
                                                                   client_instrumentinfo__provider_type='1',
                                                                   function_list__function_type='1',
                                                                   is_active=True).values_list(
            'client_instrumentinfo__pdf_data', flat=True)

        incomplete_dataextraction = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,
                                                                         client_instrumentinfo__provider_type='1',
                                                                         function_list__function_type='1',
                                                                         is_active=True).exclude(
            client_instrumentinfo__data_extraction_status='2')
        result = 'passed' if (None not in list(dataextraction_docs)) and not (incomplete_dataextraction) else 'failed'

    return result


def parse_surveyform(client, checklist_id):
    result = 'failed'
    category_list = ['previous_employment_13', 'income___expenditure_15', 'assets_24']
    income_details = {}
    surveyform = SurveyFormData.objects.filter(client_id=client.id)
    for survey in surveyform:
        if survey is not None:
            for subcategory in survey.form_data:
                label_list = subcategory['subcategory_data']
                if subcategory['subcategory_slug_name'] in category_list:
                    if subcategory['subcategory_slug_name'] == "assets_24" and checklist_id == 17:

                        asset_cash = 0
                        for label in label_list:
                            for index in range(0, len(label['sub_labels'])):
                                cash = False
                                for sublabel in (label['sub_labels'][index]['sub_label_data']):
                                    if sublabel['label_slug'] == 'type_of_asset_75' and sublabel['answer'] == 'Cash':
                                        
                                            cash = True

                                    if sublabel['label_slug'] == 'amount_128' and cash:
                                        if sublabel['answer']:
                                            asset_cash = asset_cash + Decimal(sublabel['answer'])

                            income_details['asset_cash_amount'] = asset_cash
                    else:
                        for label in label_list:
                            if label[
                                'label_slug'] == 'do_you_have_fully_funded_state_pension__66' and checklist_id == 12:
                                if not (label['answer']):
                                    return 'failed'
                                elif (label['answer']).lower() == 'yes':
                                    return 'passed'
                                elif (label['answer']).lower() == 'unsure':
                                    return 'amber'
                            if (label['label_slug'] == 'net_monthly_income_54') and checklist_id == 17:
                                if label['answer']:
                                    income_details['monthly_income'] = Decimal(label['answer'])

                    # checklist 13
                    if checklist_id == 17:
                        if income_details.get('monthly_income', None) and income_details.get('asset_cash_amount', None):
                            if Decimal(income_details.get('asset_cash_amount', None)) > 3 * Decimal(
                                    income_details.get('monthly_income', None)):
                                return "passed"

    return result


def atr_completed_check(client):
    result = 'failed'
    category = CategoryAndSubCategory.objects.filter(category_slug_name='attitude_to_risk_29').first()
    if category:
        category_summary = CategorySummary.objects.filter(client=client, category=category).first()
        if category_summary and category_summary.answered_mandatory_labels == category_summary.total_mandatory_labels:
            
            result = 'passed'
    return result


def ffr_completed_check(client):
    passed = False
    parentcategories = CategorySummary.objects.filter(client=client, category__parent=None).exclude(
        answered_mandatory_labels=F('total_mandatory_labels'))

    if not parentcategories:
        passed = True
    return passed


def check_advisor_decency(client, instrument_recommended, **kwargs):
    result = 'failed'
    advisor_decency_charge = kwargs.get('advisor_decency_charge', None)
    update_flag = kwargs.get('update_flag', None)
    advisor = Staff.objects.filter(user=instrument_recommended.client_instrumentinfo.client.created_by).first()
    if advisor_decency_charge and instrument_recommended.initial_fee <= advisor_decency_charge:
        
        result = 'passed'
    if update_flag:
        update_checklist(client, [22], result, instrument_recommended=instrument_recommended)
    else:
        update_or_create_checklist(client, 22, advisor, client_instrument=instrument_recommended.client_instrumentinfo,
                                   instrument_recommended=instrument_recommended, result=result)


def update_or_create_checklist(client, checklist_id, user, **kwargs):
    user_data = user
    print("update checklist")
    result = kwargs.get('result', None)
    is_answer = kwargs.get('is_answer', None)
    client_instrument = kwargs.get('client_instrument', None)
    instrument_recommended = kwargs.get('instrument_recommended', None)
    user = Staff.objects.filter(user=client.created_by).first()
    extraction_doccheck = True
    compliance = None
    administrator = None
    checklist_exists = None
    reset_verification_flag = False
    draftchecklist = DraftCheckList.objects.filter(id=checklist_id).first()
    if draftchecklist:
        if draftchecklist.id == 7:
            checklist_exist = ClientCheckList.objects.filter(draft_checklist=draftchecklist, client=client,
                                                             user=user).first()
            if not checklist_exist:
                if user.advisor_terms_and_agreement:
                    result = 'passed'
                else:
                    result = 'failed'
            else:
                result = 'no_update'
        if draftchecklist.id in [8, 9, 10, 13, 14, 15, 16,18]:  # 8#Is the client’s investment experience and knowledge recorded?
            result = atr_completed_check(client)
        if draftchecklist.id == 11:
            print("in checklist 11")
            if not result:
                atr_doc = Document.objects.filter(owner=client, doc_type='11', is_active=True).last()
                result = 'passed' if atr_doc else 'failed'
        if draftchecklist.id in [17, 12]:  # Is there a sufficient emergency fund?
            result = parse_surveyform(client, draftchecklist.id)
        if draftchecklist.id in [19, 20, 21, 23, 49]:  # Has a critical yield comparison been carried out and on file?
            result = draftupdate_check(client, draftchecklist.id)
        if draftchecklist.id == 29:  # Dates of documents being produced in order  (LOA, Illustration, ATP, app summary, SR)
            result = 'passed'  # Always true
        if draftchecklist.id == 30:  # Is there sufficient information to justify the advice ?
            print("in checklist 30")
            illustration_application_check = True
            dataextraction_docs = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,
                                                                       client_instrumentinfo__provider_type='1',
                                                                       is_active=True).values_list('client_instrumentinfo__pdf_data', flat=True)
            transfer_instruments = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,
                                                                        is_active=True).exclude(map_transfer_from=None).values_list('map_transfer_from', flat=True).distinct()

            instrumentslist = InstrumentsRecomended.objects.filter(client_instrumentinfo__client=client,
                                                                   client_instrumentinfo__provider__in=[10, 12],
                                                                   is_clone=False, is_active=True).exclude(id__in=list(transfer_instruments))
            for instrument in instrumentslist:
                # if instrument.client_instrumentinfo.illustration  and instrument.client_instrumentinfo.app_summary:
                if instrument.client_instrumentinfo.illustration:
                    continue
                else:
                    illustration_application_check = False
                    break

            if dataextraction_docs:
                if None in dataextraction_docs:
                    extraction_doccheck = False
            result = 'passed' if (extraction_doccheck and illustration_application_check and (
                ffr_completed_check(client))) else 'failed'
        if draftchecklist.id in [31,32]:  # Is the client a vulnerable client?#Is the client being classified other than a retail client?
            result = 'amber' if is_answer == True else 'passed'

        if draftchecklist.id == 41:  # Has the client’s ATR been increased/decreased to meet a specific need/objective?
            checklist_present = ClientCheckList.objects.filter(draft_checklist=draftchecklist, client=client,
                                                               user=user).first()
            result = 'passed' if not checklist_present else 'no_update'

        if draftchecklist.id == 47 and not result:
            
            result = 'failed'

        if draftchecklist.id == 52 and not result:
            
            result = 'passed' if is_answer == True else 'amber'

        if draftchecklist.checklist_group == 'Compliance':
            compliance = Staff.objects.filter(user__groups__name='Compliance', company=user.company_id).first()
    # Reset verfication flag
    clienttask = ClientTask.objects.filter(client=client).exclude(task_status='3').last()
    if clienttask:
        checklist_exists = ClientCheckList.objects.filter(draft_checklist=draftchecklist, client=client,
                                                          user=user).first()
        if draftchecklist.checklist_group == 'Compliance':
            administrator = clienttask.administrator

    if result == 'passed':
        client_checklist1, created = ClientCheckList.objects.update_or_create(draft_checklist=draftchecklist,
                                                                              client=client,
                                                                              owner_group=draftchecklist.checklist_group,
                                                                              user=user,
                                                                              client_instrument=client_instrument,
                                                                              instrument_recommended=instrument_recommended,
                                                                              defaults={'colour_code': 'Green',
                                                                                        'administrator': administrator,
                                                                                        'compliance': compliance}, )
    elif result == 'amber':
        if checklist_exists and not (checklist_exists.colour_code == 'Amber'):
            
            reset_verification_flag = True

        client_checklist1, created = ClientCheckList.objects.update_or_create(draft_checklist=draftchecklist,
                                                                              client=client,
                                                                              owner_group=draftchecklist.checklist_group,
                                                                              user=user,
                                                                              client_instrument=client_instrument,
                                                                              instrument_recommended=instrument_recommended,
                                                                              defaults={'colour_code': 'Amber',
                                                                                        'administrator': administrator,
                                                                                        'compliance': compliance}, )
        if created:
            reset_verification_flag = True

    elif result == 'failed':

        if checklist_exists and not (checklist_exists.colour_code == 'Red'):
           
            reset_verification_flag = True

        client_checklist1, created = ClientCheckList.objects.update_or_create(draft_checklist=draftchecklist,
                                                                              client=client,
                                                                              owner_group=draftchecklist.checklist_group,
                                                                              user=user,
                                                                              client_instrument=client_instrument,
                                                                              instrument_recommended=instrument_recommended,
                                                                              defaults={'colour_code': 'Red',
                                                                                        'administrator': administrator,
                                                                                        'compliance': compliance}, )
        if created:
            reset_verification_flag = True

    elif result == None:
        delete_checklist(client, draftchecklist, client_instrument=client_instrument)

    ########REsetting the verfication flag################
    if clienttask:
        if reset_verification_flag:
            if draftchecklist.checklist_group == 'Advisor':
                if clienttask.is_advisor_checklist_verified:
                    clienttask.is_advisor_checklist_verified = False
            elif draftchecklist.checklist_group == 'Compliance':
                if clienttask.is_admin_checklist_verified:
                    clienttask.is_admin_checklist_verified = False
                if clienttask.is_compliance_checklist_verified:
                    clienttask.is_compliance_checklist_verified = False

        clienttask.save()


def update_checklist(client, check_list, result, **kwargs):
    # Reset verfication flag
    client_instrument = kwargs.get('client_instrument', None)
    instrument_recommended = kwargs.get('instrument_recommended', None)
    check_list_exists = None
    clienttask = ClientTask.objects.filter(client=client).exclude(task_status='3').last()
    if clienttask:
        check_list_exists = ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client)
    if result == 'passed':
        if instrument_recommended:
            ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client,instrument_recommended=instrument_recommended).update(colour_code='Green')
        else:
            ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client,client_instrument=client_instrument).update(colour_code='Green')

    elif result == 'failed':
        if check_list_exists:
            for clientcheck in check_list_exists:
                if not (clientcheck.colour_code == 'Red') and clienttask:
                    if clientcheck.draft_checklist.checklist_group == 'Advisor':
                        if clienttask.is_advisor_checklist_verified:
                            clienttask.is_advisor_checklist_verified = False
                    elif clientcheck.draft_checklist.checklist_group == 'Compliance':
                        if clienttask.is_admin_checklist_verified:
                            clienttask.is_admin_checklist_verified = False
                        if clienttask.is_compliance_checklist_verified:
                            clienttask.is_compliance_checklist_verified = False
                    clienttask.save()
        if instrument_recommended:
            ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client,instrument_recommended=instrument_recommended).update(colour_code='Red')
        else:
            ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client,client_instrument=client_instrument).update(colour_code='Red')

    elif result == 'amber':
        if check_list_exists:
            for clientcheck in check_list_exists:
                if not (clientcheck.colour_code == 'Amber') and clienttask:
                    if clientcheck.draft_checklist.checklist_group == 'Advisor':
                        if clienttask.is_advisor_checklist_verified:
                            clienttask.is_advisor_checklist_verified = False
                    elif clientcheck.draft_checklist.checklist_group == 'Compliance':
                        if clienttask.is_admin_checklist_verified:
                            clienttask.is_admin_checklist_verified = False
                        if clienttask.is_compliance_checklist_verified:
                            clienttask.is_compliance_checklist_verified = False
                    clienttask.save()
        if instrument_recommended:
            ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client,instrument_recommended=instrument_recommended).update(
                colour_code='Amber')
        else:
            ClientCheckList.objects.filter(draft_checklist__in=check_list, client=client,client_instrument=client_instrument).update(
                colour_code='Amber')


def delete_checklist(client, checklist, **kwargs):
    client_instrument = kwargs.get('client_instrument', None)
    instrument_recommended = kwargs.get('instrument_recommended', None)
    if client_instrument:
        if isinstance(client_instrument, list):
            ClientCheckList.objects.filter(draft_checklist=checklist, client=client,
                                                        client_instrument__in=client_instrument).update(is_deleted=True)
        else:
            if instrument_recommended:
                ClientCheckList.objects.filter(draft_checklist=checklist, client=client,
                                                            client_instrument=client_instrument,
                                                            instrument_recommended=instrument_recommended).update(
                    is_deleted=True)
            else:
                ClientCheckList.objects.filter(draft_checklist=checklist, client=client,
                                                            client_instrument=client_instrument).update(is_deleted=True)
    else:
        ClientCheckList.objects.filter(draft_checklist=checklist, client=client).update(is_deleted=True)

