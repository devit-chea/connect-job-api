import json
from django.db.utils import IntegrityError
from rest_framework import status

from apps.base.models.institution_model import Institution

def create_institutions_from_json(file_path, serializer_class, create_uid):
    """
    Reads institution data from a JSON file, checks for existing institutions 
    by 'name', and creates new ones if they don't exist.
    """
    # Use a set to track names in the JSON to avoid redundant checks/saves
    # within the loop, although the main check is against the DB.
    
    try:
        with open(file_path, encoding="utf8") as file:
            contents = json.load(file)
    except FileNotFoundError:
        # Handle case where the file doesn't exist
        return {"status": status.HTTP_404_NOT_FOUND, "message": "Institutions data file not found."}
    except json.JSONDecodeError:
        # Handle case where the file is not valid JSON
        return {"status": status.HTTP_400_BAD_REQUEST, "message": "Invalid JSON format in institutions data file."}

    created_count = 0
    skipped_count = 0
    errors = []
    
    # Pre-fetch existing institution names to minimize database queries inside the loop
    # Assuming 'Institution' model is imported
    existing_names = set(Institution.objects.values_list('name', flat=True))

    for content in contents:
        institution_name = content.get('name') # Assuming 'name' is the key for the institution name
        
        if not institution_name:
            errors.append({"data": content, "error": "Institution data is missing a 'name' field."})
            continue

        # Check if name exists in the database
        if institution_name in existing_names:
            skipped_count += 1
            # Optional: Log that it was skipped
            print(f"Skipped institution: '{institution_name}' (Already exists).")
            continue

        # Validation and Saving
        serializer = serializer_class(data=content)
        if serializer.is_valid():
            try:
                # Add the new name to the set so subsequent entries with the 
                # same name in the JSON file will also be skipped.
                existing_names.add(institution_name) 
                
                # Save the institution
                serializer.save(create_uid=create_uid)
                created_count += 1
            except IntegrityError as e:
                # This could catch race conditions or other database unique constraints
                errors.append({"data": content, "error": f"Database integrity error: {e}"})
                # If it's a unique constraint violation on 'name', the name is now in DB, 
                # but we'll re-check via the set on next iteration.
            except Exception as e:
                errors.append({"data": content, "error": f"An unexpected error occurred during save: {e}"})
        else:
            errors.append({"data": content, "error": serializer.errors})

    # Return a summary of the operation
    if errors:
         return {
            "status": status.HTTP_207_MULTI_STATUS, # Use 207 for partial success/failure
            "message": f"Operation completed with {created_count} created, {skipped_count} skipped, and {len(errors)} errors.",
            "details": {"created": created_count, "skipped": skipped_count, "errors": errors}
        }
    
    return {
        "status": status.HTTP_201_CREATED,
        "message": f"Successfully created {created_count} institutions. {skipped_count} institutions were skipped.",
        "details": {"created": created_count, "skipped": skipped_count}
    }