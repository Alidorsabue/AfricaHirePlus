from rest_framework import serializers
from .models import Test, Section, Question, CandidateTestResult


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'title', 'order']
        read_only_fields = ['id']


class QuestionSerializer(serializers.ModelSerializer):
    section_title = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'section',
            'section_title',
            'question_type',
            'text',
            'options',
            'correct_answer',
            'points',
            'order',
            'attachment',
            'code_language',
            'starter_code',
        ]
        read_only_fields = ['id', 'attachment']

    def get_section_title(self, obj):
        if obj.section_id:
            return obj.section.title if hasattr(obj, 'section') and obj.section else ''
        return getattr(obj, 'section_title', '') or ''


class QuestionWriteSerializer(serializers.ModelSerializer):
    """Création/édition de questions. section_index = index dans la liste sections (0-based)."""
    section_index = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Question
        fields = [
            'id',
            'question_type',
            'text',
            'options',
            'correct_answer',
            'points',
            'order',
            'code_language',
            'starter_code',
            'section_index',
        ]
        read_only_fields = ['id']
        extra_kwargs = {'text': {'required': True}}


class TestSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = Test
        fields = [
            'id', 'company', 'job_offer', 'title', 'description', 'test_type',
            'duration_minutes', 'passing_score', 'access_code', 'is_active',
            'sections', 'questions', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'access_code']


class SectionWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    order = serializers.IntegerField(default=0, min_value=0)


class TestWriteSerializer(serializers.ModelSerializer):
    """Création test avec sections et questions (nested)."""
    sections = SectionWriteSerializer(many=True, required=False)
    questions = QuestionWriteSerializer(many=True, required=False)

    class Meta:
        model = Test
        fields = [
            'id', 'company', 'job_offer', 'title', 'description', 'test_type',
            'duration_minutes', 'passing_score', 'access_code', 'is_active',
            'sections', 'questions', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'company': {'required': False},
            'access_code': {'required': False},
        }

    def create(self, validated_data):
        sections_data = validated_data.pop('sections', [])
        questions_data = validated_data.pop('questions', [])
        instance = Test.objects.create(**validated_data)
        created_sections = []
        for s in sorted(sections_data, key=lambda x: x.get('order', 0)):
            sec = Section.objects.create(test=instance, title=s['title'], order=s.get('order', len(created_sections)))
            created_sections.append(sec)
        for q in questions_data:
            q = dict(q)
            section_index = q.pop('section_index', None)
            q.pop('id', None)
            section_id = None
            if section_index is not None and 0 <= section_index < len(created_sections):
                section_id = created_sections[section_index].id
            Question.objects.create(test=instance, section_id=section_id, **q)
        return instance

    def update(self, instance, validated_data):
        sections_data = validated_data.pop('sections', None)
        questions_data = validated_data.pop('questions', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        created_sections = []
        if sections_data is not None:
            instance.sections.all().delete()
            for s in sorted(sections_data, key=lambda x: x.get('order', 0)):
                sec = Section.objects.create(test=instance, title=s['title'], order=s.get('order', len(created_sections)))
                created_sections.append(sec)
        if questions_data is not None:
            if not created_sections:
                created_sections = list(instance.sections.order_by('order', 'id'))
            instance.questions.all().delete()
            for q in questions_data:
                q = dict(q)
                section_index = q.pop('section_index', None)
                q.pop('id', None)
                section_id = None
                if section_index is not None and 0 <= section_index < len(created_sections):
                    section_id = created_sections[section_index].id
                Question.objects.create(test=instance, section_id=section_id, **q)
        return instance


class CandidateTestResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateTestResult
        fields = [
            'id', 'application', 'test', 'status', 'score', 'max_score',
            'answers', 'started_at', 'submitted_at',
            'tab_switch_count', 'is_flagged', 'is_completed',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubmitTestAnswersSerializer(serializers.Serializer):
    """Soumission des réponses à un test (answers = { question_id: value })."""
    application_id = serializers.IntegerField()
    test_id = serializers.IntegerField()
    answers = serializers.JSONField(help_text='{"1": "a", "2": ["a","b"]}')
