from rest_framework import serializers
from .models import SurveyFormData




class SurveyFormDataSerializer(serializers.ModelSerializer):
    data=serializers.SerializerMethodField()
    class Meta:
        model = SurveyFormData
        fields = ('id','client_id','client','advisor_id','category_id','category','data')



    def get_data(self, obj):
        return obj.form_data

    def create(self, validated_data):
        """
        Overriding the default create method of the Model serializer.
        :param validated_data: data containing all the details of client
        :return: returns a successfully created client record
        """
        print("inside serialzer")
        print(validated_data)
        try:
            print(validated_data['id'])
            surveyform=SurveyFormData.objects.get(id=validated_data['id'])
            print(surveyform)
        except Exception as e:
            print("inside except"+str(e))
            
