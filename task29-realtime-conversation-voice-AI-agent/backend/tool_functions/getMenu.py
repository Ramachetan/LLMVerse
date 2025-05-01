import copy

def getMenu(dietary_restrictions=None):
    """
    Generates an Andhra-style menu, optionally filtering based on dietary restrictions.

    Args:
        dietary_restrictions (list, optional): A list of strings representing
                                               dietary restrictions (e.g., ['vegetarian', 'gluten-free']).
                                               Defaults to None (no restrictions).
                                               Supported restrictions: 'vegetarian', 'vegan',
                                               'gluten-free', 'nut-free'.

    Returns:
        dict: A dictionary representing the filtered Andhra menu, categorized by course.
              Returns an empty dictionary if no items match the restrictions.
    """
    if dietary_restrictions is None:
        dietary_restrictions = []
    # Normalize restrictions to lowercase for consistent checking
    dietary_restrictions = [restriction.lower() for restriction in dietary_restrictions]

    # --- Base Andhra Menu Definition ---
    # Each dish has a name and a list of tags indicating its properties.
    # Tags help in filtering based on dietary needs.
    base_menu = {
        "Appetizers": [
            {"name": "Punugulu (Lentil Fritters)", "tags": ["veg", "contains_gluten"]}, # Often made with rice+urad, but sometimes semolina/maida added
            {"name": "Mirapakaya Bajji (Chilli Fritters)", "tags": ["veg", "contains_gluten"]}, # Batter usually contains besan (GF) but check for wheat flour addition
            {"name": "Chicken 65", "tags": ["non-veg", "contains_gluten"]}, # Coating often contains flour
            {"name": "Royyala Vepudu (Prawn Fry)", "tags": ["non-veg", "gluten-free", "nut-free"]},
            {"name": "Mokka Jonna Garelu (Corn Vada)", "tags": ["veg", "gluten-free", "nut-free"]}, # Generally GF
        ],
        "Main Course - Rice": [
            {"name": "Steamed Rice (Annam)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Gongura Pulihora (Sorrel Leaf Rice)", "tags": ["veg", "vegan", "gluten-free"]}, # Tempering might contain nuts
            {"name": "Tomato Rice", "tags": ["veg", "vegan", "gluten-free"]}, # Tempering might contain nuts
            {"name": "Andhra Chicken Biryani", "tags": ["non-veg", "gluten-free"]}, # Check for nut garnish
            {"name": "Mutton Biryani", "tags": ["non-veg", "gluten-free"]}, # Check for nut garnish
        ],
        "Main Course - Roti/Bread": [
            # Note: Rotis are typically not central to a traditional Andhra meal served with rice, but included for variety
            {"name": "Plain Roti/Chapati", "tags": ["veg", "vegan", "contains_gluten", "nut-free"]},
            {"name": "Pesarattu (Moong Dal Dosa)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Dibba Rotti (Thick Rice & Lentil Pancake)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
        ],
        "Main Course - Curries/Sides (Veg)": [
            {"name": "Gutti Vankaya Kura (Stuffed Brinjal)", "tags": ["veg", "vegan", "gluten-free", "contains_nuts"]}, # Stuffing often contains peanuts/sesame/coconut
            {"name": "Bendakaya Fry (Okra Fry)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Dondakaya Fry (Ivy Gourd Fry)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Beerakaya Kura (Ridge Gourd Curry)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]}, # Can sometimes contain nuts/dairy
            {"name": "Gutti Beerakaya (Stuffed Ridge Gourd)", "tags": ["veg", "vegan", "gluten-free", "contains_nuts"]}, # Stuffing often contains nuts
            {"name": "Muddha Pappu (Plain Toor Dal)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]}, # Often served with Ghee (added separately)
            {"name": "Tomato Pappu (Tomato Dal)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Palakura Pappu (Spinach Dal)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Dosakaya Pappu (Yellow Cucumber Dal)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
        ],
        "Main Course - Curries/Sides (Non-Veg)": [
            {"name": "Andhra Kodi Kura (Chicken Curry)", "tags": ["non-veg", "gluten-free", "nut-free"]}, # Can sometimes contain nuts/coconut
            {"name": "Gongura Mamsam (Mutton with Sorrel Leaves)", "tags": ["non-veg", "gluten-free", "nut-free"]},
            {"name": "Chepala Pulusu (Fish Tamarind Curry)", "tags": ["non-veg", "gluten-free", "nut-free"]},
            {"name": "Royyala Iguru (Prawn Curry)", "tags": ["non-veg", "gluten-free", "nut-free"]},
        ],
         "Rasam / Sambar": [
            {"name": "Tomato Rasam / Charu", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Miriyala Rasam (Pepper Rasam)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Sambar", "tags": ["veg", "vegan", "gluten-free", "nut-free"]}, # Traditionally vegan, check tempering/garnish
        ],
        "Pachadi / Chutney": [
            {"name": "Gongura Pachadi", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Dosakaya Pachadi (Yellow Cucumber Chutney)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Tomato Pachadi", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
            {"name": "Kobbari Pachadi (Coconut Chutney)", "tags": ["veg", "vegan", "gluten-free", "contains_nuts"]}, # Coconut is botanically a drupe, but often restricted in nut allergies
            {"name": "Perugu Pachadi (Yogurt Raita)", "tags": ["veg", "contains_dairy", "gluten-free", "nut-free"]},
        ],
        "Dessert": [
            {"name": "Boorelu (Lentil & Jaggery Fritters)", "tags": ["veg", "contains_gluten", "contains_dairy", "nut-free"]}, # Contains ghee, batter often has wheat/semolina
            {"name": "Semiya Payasam (Vermicelli Kheer)", "tags": ["veg", "contains_gluten", "contains_dairy", "contains_nuts"]}, # Contains milk, nuts, wheat vermicelli
            {"name": "Double Ka Meetha (Bread Pudding)", "tags": ["veg", "contains_gluten", "contains_dairy", "contains_nuts"]}, # Bread, milk, nuts
            {"name": "Rava Kesari (Semolina Halwa)", "tags": ["veg", "contains_gluten", "contains_dairy", "contains_nuts"]}, # Semolina (wheat), ghee, nuts
            {"name": "Poornam Boorelu", "tags": ["veg", "contains_dairy", "gluten-free", "nut-free"]}, # Outer shell GF, contains ghee
            {"name": "Fresh Fruit Salad", "tags": ["veg", "vegan", "gluten-free", "nut-free"]},
        ],
        "Accompaniments": [
            {"name": "Ghee (Neyyi)", "tags": ["veg", "contains_dairy", "gluten-free", "nut-free"]},
            {"name": "Mango Pickle (Avakaya)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]}, # Check oil type if specific allergy
            {"name": "Yogurt (Perugu)", "tags": ["veg", "contains_dairy", "gluten-free", "nut-free"]},
            {"name": "Appadam / Vadiyalu (Papad / Sun-dried Lentil Fritters)", "tags": ["veg", "vegan", "gluten-free", "nut-free"]}, # Check ingredients & frying medium
            {"name": "Podis (Spice Powders - e.g., Kandi Podi)", "tags": ["veg", "vegan", "gluten-free"]}, # Might contain nuts depending on the podi
        ]
    }

    # --- Filtering Logic ---
    filtered_menu = copy.deepcopy(base_menu) # Start with a full copy

    for category, items in base_menu.items():
        items_to_keep = []
        for item in items:
            tags = item["tags"]
            keep = True # Assume we keep the item unless a restriction filters it out

            # Check against each restriction
            if 'vegetarian' in dietary_restrictions and 'non-veg' in tags:
                keep = False
            if 'vegan' in dietary_restrictions and ('non-veg' in tags or 'contains_dairy' in tags):
                keep = False
            if 'gluten-free' in dietary_restrictions and 'contains_gluten' in tags:
                keep = False
            if 'nut-free' in dietary_restrictions and 'contains_nuts' in tags:
                keep = False
                # Also check common nut additions not explicitly tagged (optional, based on how strict you need it)
                # e.g., if 'nut-free' in dietary_restrictions and 'Pulihora' in item['name'] or 'Biryani' in item['name']:
                #    print(f"Warning: {item['name']} might contain nuts in tempering/garnish. Verify preparation.")


            if keep:
                items_to_keep.append(item)

        # Update the category in the filtered menu
        if items_to_keep:
            filtered_menu[category] = items_to_keep
        else:
            # Remove category if no items match
            del filtered_menu[category]

    return filtered_menu
