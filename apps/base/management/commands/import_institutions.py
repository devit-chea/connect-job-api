import os

from django.core.management.base import BaseCommand, CommandError

from apps.base.serializers.institution_serializer import InstitutionSerializer
from apps.base.services.institution_service import create_institutions_from_json

class Command(BaseCommand):
    # This text is displayed when the user runs 'python manage.py help import_institutions'
    help = 'Imports institution data from the default JSON file, skipping existing ones by name.'

    def add_arguments(self, parser):
        # Optional: Allow the user to specify a different file path
        parser.add_argument(
            '--file',
            type=str,
            default='apps/base/data/institutions.json',
            help='The path to the JSON file to import.',
        )
        
        # Optional: Allow the user to specify the create_uid (e.g., a system user ID)
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='The user ID to set as the create_uid for new records.',
        )

    def handle(self, *args, **options):
        file_path = options['file']
        create_uid = options['user_id']
        
        # Check if the file exists before running the service logic
        if not os.path.exists(file_path):
            raise CommandError(f'File not found at path: {file_path}')

        # Use the provided service function
        self.stdout.write(f"Starting import from: {file_path}")
        
        # We pass the required dependencies: file_path, the Serializer class, and the user ID
        result = create_institutions_from_json(
            file_path=file_path,
            serializer_class=InstitutionSerializer,
            create_uid=create_uid
        )

        # Output the results of the service function
        
        # Use self.stdout.write with self.style.SUCCESS for successful messages
        if result['status'] in (201, 207):
            self.stdout.write(self.style.SUCCESS(result['message']))
        else:
             # Use self.style.ERROR or self.style.WARNING for issues
            self.stdout.write(self.style.ERROR(result['message']))
            
        # Log details if provided (especially errors)
        if 'details' in result and result['details'].get('errors'):
            self.stdout.write(self.style.WARNING(f"\n--- {len(result['details']['errors'])} ERRORS/FAILURES ENCOUNTERED ---"))
            for error in result['details']['errors']:
                # Output a structured error message
                self.stdout.write(f"  Data: {error.get('data', 'N/A')}")
                self.stdout.write(self.style.ERROR(f"  Error: {error.get('error', 'Unknown Error')}"))
            self.stdout.write("\n")
            
        self.stdout.write(f"Summary: Created {result['details'].get('created', 0)}, Skipped {result['details'].get('skipped', 0)}.")