from django.core.management.base import BaseCommand
from ...models import MasterKeywords


class Command(BaseCommand):
    help = '''create user group   ----    ./manage.py initial_setup '''

    def handle(self, *args, **kw):
        keyword_list = {'start_date':'Start date', 'fund_value':'Fund Value' ,'transfer_value':'Transfer Value', 'monthly_contirbution':'Monthly Contributions', 'charges':'Charges', 
        				'rebate':'Rebates/Discounts', 'invested_in':'Invested in', 'no_of_funds_available':'Number of funds available', 'drawdown_ready':'Drawdown ready?', 'tax_free_cash':'Tax free cash', 
        				'gurantees':'Guarantees', 'partial_transfer':'Partial Transfer', 'policy_no':'Policy Number' }

        for slug, value in keyword_list.items():
            print(value , ' added  ')
            status, entry_created = MasterKeywords.objects.update_or_create(keyword=value, keyword_slug=slug, document_type='1')

        self.stdout.write(self.style.SUCCESS('Successfully added Master Keywords'))


