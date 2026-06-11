from django.db.models import Q


@staticmethod
def search_by_fullname(query_string, applied_state_records):
        
    keywords = query_string.split()
    # 2. Build a Q object for filtering by full_name
    full_name_query = Q()

    # Create an OR condition for each keyword
    for keyword in keywords:
        full_name_query |= Q(user_company_profile__profile__full_name__icontains=keyword)

    # 3. Apply the full_name filter to the base queryset
    filtered_applicants = applied_state_records.filter(full_name_query)
    
    return filtered_applicants