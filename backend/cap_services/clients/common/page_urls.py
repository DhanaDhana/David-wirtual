from ..models import ActivityFlow, Provider, Reminder, Client
from cap_outlook_service.outlook_services.models import MailFolder


URL_DICT = {'instrument':'/client-management/products-list', 'surveyform': '/client-management/survey-form', 'mail': '/mail/sent-items', 'meeting': '/calendar', 'profile': '/client-management/client-profile', 'client_task':'/task-details'}


def get_page_url(**kwargs):
	client = kwargs.get('client', None)
	status = kwargs.get('status', None)
	instrument = kwargs.get('instrument', None)
	user = kwargs.get('user', None)
	voice_category = kwargs.get('voice_category', None)
	client_task = kwargs.get('client_task', None)
	task_collection = kwargs.get('task_collection', None)

	data = {"redirect_url" : None , "redirect_data" : None }
	position_dict = { 'personal information' : 0, 'occupation info' : 1, 'income & expenditure summary':2, 'networth summary':3, 'plans & atr':4, 'plans&atr':4 }
	position = None

	if client_task:
		if task_collection.task_collection.task_slug in ['meeting_scheduled','meeting_cancelled','meeting_rescheduled']:
			data['redirect_url'] = URL_DICT['meeting']
		else:
			data['redirect_url'] = URL_DICT['client_task'] + '/'+str(client_task.id)
			data['redirect_data'] = { 'clientId' : client.id }

	elif status:
		status_name = status.get_status_name_display()
		context = status_name.split('_')[0]
		category = status_name.split('_')[-1]
		if context.lower() == 'surveyform':
			#should redirect to survery form. so add url of survery form
			url = URL_DICT[context.lower()]
			if category.lower() in position_dict.keys():
				position = position_dict.get(category.lower())
				redirect_data = { 'clientId' : client.id, 'position': position }
				data['redirect_url'] = url
				data['redirect_data'] = redirect_data

		if context.lower() == 'instrument':
			url = URL_DICT[context.lower()]
			redirect_data = { 'clientId' : client.id }
			data['redirect_url'] = url
			data['redirect_data'] = redirect_data

		if context.lower() == 'mail sent':
			sent_item_folder = MailFolder.objects.filter(user=user, folder_name='Sent Items').first()
			if sent_item_folder:
				url = URL_DICT['mail']+'/'+str(sent_item_folder.id)+'/'
				data['redirect_url'] = url

		if context.lower() == 'meeting request':
			url = URL_DICT['meeting']
			data['redirect_url'] = url

		if (context.lower() == 'voice record') and voice_category:
			url = URL_DICT['surveyform']
			position = position_dict.get(voice_category.lower())
			if voice_category.lower() in position_dict.keys():
				redirect_data = { 'clientId' : client.id, 'position': position }
				data['redirect_url'] = url
				data['redirect_data'] = redirect_data

		if context.lower() == 'client add':
			url = URL_DICT['profile']
			redirect_data = { 'clientId' : client.id }
			data['redirect_url'] = url
			data['redirect_data'] = redirect_data

	return data