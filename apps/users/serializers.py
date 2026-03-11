"""
Sérialiseurs utilisateurs : profil (UserSerializer), inscription (Register, Company, Recruiter, Candidate).
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.companies.models import Company

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Lecture et mise à jour du profil utilisateur (champs non sensibles)."""
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'company', 'phone', 'avatar', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined', 'role', 'company']


class ChangePasswordSerializer(serializers.Serializer):
    """Changement de mot de passe pour l'utilisateur connecté."""
    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)
    new_password_confirm = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        if data['new_password'] != data.get('new_password_confirm'):
            raise serializers.ValidationError({
                'new_password_confirm': 'Les mots de passe ne correspondent pas.'
            })
        return data

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Mot de passe actuel incorrect.')
        return value


class RegisterSerializer(serializers.ModelSerializer):
    """Inscription générique (recruteur ou super admin selon payload)."""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'role', 'company', 'phone',
        ]

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas.'})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=validated_data.get('role', User.Role.RECRUITER),
            company=validated_data.get('company'),
            phone=validated_data.get('phone', ''),
        )
        return user


# --- Inscription candidat ---

class RegisterCandidateSerializer(serializers.Serializer):
    """Création d'un compte candidat (pour voir les offres et postuler)."""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('Un compte existe déjà avec cet email.')
        return value

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas.'})
        return data

    def create(self, validated_data):
        email = validated_data['email']
        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=User.Role.CANDIDATE,
            company=None,
            phone=validated_data.get('phone', ''),
        )
        return user


# --- Inscription entreprise : Company + premier recruteur ---

class RegisterCompanySerializer(serializers.Serializer):
    """Création entreprise + premier compte recruteur."""
    company_name = serializers.CharField(max_length=255)
    company_slug = serializers.SlugField(max_length=100, required=False, allow_blank=True)
    company_website = serializers.URLField(required=False, allow_blank=True)
    company_email = serializers.EmailField(required=False, allow_blank=True)
    company_country = serializers.CharField(max_length=100, required=False, allow_blank=True)

    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Ce nom d\'utilisateur est déjà pris.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Un compte existe déjà avec cet email.')
        return value

    def validate_company_slug(self, value):
        if value and Company.objects.filter(slug=value).exists():
            raise serializers.ValidationError('Ce slug entreprise est déjà utilisé.')
        return value

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas.'})
        from django.utils.text import slugify
        slug = data.get('company_slug') or slugify(data.get('company_name', ''))[:100]
        data['company_slug'] = slug or 'company'
        if Company.objects.filter(slug=data['company_slug']).exists():
            import uuid
            data['company_slug'] = f"{data['company_slug']}-{uuid.uuid4().hex[:8]}"
        return data

    def create(self, validated_data):
        company = Company.objects.create(
            name=validated_data['company_name'],
            slug=validated_data['company_slug'],
            website=validated_data.get('company_website', ''),
            email=validated_data.get('company_email', ''),
            country=validated_data.get('company_country', ''),
        )
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=User.Role.RECRUITER,
            company=company,
            phone=validated_data.get('phone', ''),
        )
        return {'user': user, 'company': company}


# --- Inscription recruteur (ajout à une entreprise existante) ---

class RegisterRecruiterSerializer(serializers.Serializer):
    """Création d'un recruteur pour une entreprise existante (réservé Admin)."""
    company = serializers.PrimaryKeyRelatedField(queryset=Company.objects.all())
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Ce nom d\'utilisateur est déjà pris.')
        return value

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Un compte existe déjà avec cet email.')
        return value

    def validate(self, data):
        if data['password'] != data.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Les mots de passe ne correspondent pas.'})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role=User.Role.RECRUITER,
            company=validated_data['company'],
            phone=validated_data.get('phone', ''),
        )
        return user
