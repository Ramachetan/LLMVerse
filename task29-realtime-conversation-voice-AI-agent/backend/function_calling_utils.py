import logging
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



def getMenu(cuisine: str = None, dietary_restrictions: str = None) -> str:
    """
    Retrieves the restaurant menu, optionally filtering by cuisine and dietary needs.

    Args:
        cuisine: The type of cuisine requested (e.g., 'Andhra Cafe').
        dietary_restrictions: Any dietary needs (e.g., 'vegetarian', 'gluten-free', 'vegan').

    Returns:
        A string describing the menu items available.
    """
    logger.info(f"Executing getMenu function call with cuisine='{cuisine}', restrictions='{dietary_restrictions}'")

    # --- Mock Menu Data (Replace with actual data source like DB or API call) ---
    full_menu = {
        "Andhra Cafe": {
            "Starters (Tiffins)": [
                "Idli with Sambar & Chutney (Vegetarian, Gluten-Free, Vegan option available)",
                "Vada with Sambar & Chutney (Vegetarian, Gluten-Free, Vegan option available)",
                "Plain Dosa (Vegetarian, Gluten-Free, Vegan)",
                "Masala Dosa (Vegetarian, Gluten-Free, Vegan option available)",
                "Upma (Vegetarian, Vegan option available, Contains Nuts - specify nut-free)",
                "Pesarattu (Green Gram Dosa) (Vegetarian, Gluten-Free, Vegan)",
                "Punugulu (Deep Fried Rice/Lentil Dumplings) (Vegetarian)",
            ],
            "Main Courses (Meals & Curries)": [
                "Andhra Veg Meals (Thali) (Vegetarian, Vegan option available, Gluten-Free option available)",
                "Gongura Pappu (Sorrel Leaves Dal) (Vegetarian, Gluten-Free, Vegan)",
                "Gutti Vankaya Kura (Stuffed Eggplant Curry) (Vegetarian, Contains Nuts - specify nut-free)",
                "Tomato Pappu (Tomato Dal) (Vegetarian, Gluten-Free, Vegan)",
                "Vegetable Biryani (Vegetarian, Gluten-Free option available, Vegan option available)",
                "Chicken Fry Piece Biryani (Halal)",
                "Andhra Chicken Curry (Halal, Gluten-Free option available)",
                "Chepala Pulusu (Fish Curry) (Gluten-Free option available)"
            ],
            "Sides & Breads": [
                "White Rice (Vegetarian, Vegan, Gluten-Free)",
                "Chapati (Vegetarian, Vegan option available)",
                "Papad (Vegetarian, Vegan, Gluten-Free)",
                "Curd (Yogurt) (Vegetarian, Gluten-Free)"
            ],
            "Desserts": [
                "Double Ka Meetha (Bread Pudding) (Vegetarian, Contains Dairy, Contains Nuts)",
                "Semiya Payasam (Vermicelli Kheer) (Vegetarian, Contains Dairy, Contains Nuts, Vegan option available)",
                "Bobbatlu (Sweet Flatbread) (Vegetarian, Contains Gluten, Contains Dairy)"
            ],
            "Beverages": [
                "Filter Coffee (Vegetarian, Contains Dairy)",
                "Masala Chai (Tea) (Vegetarian, Contains Dairy, Vegan option available)",
                "Mango Lassi (Vegetarian, Contains Dairy, Gluten-Free)",
                "Buttermilk (Majjiga) (Vegetarian, Contains Dairy, Gluten-Free)"
            ]
        }
        # Add more cuisines as needed
    }

    # --- Filtering Logic ---
    menu_to_return = {}
    available_cuisines = list(full_menu.keys())
    selected_cuisine_name = "the requested" # Default description

    # Determine base menu based on cuisine
    if cuisine and cuisine.capitalize() in full_menu:
        menu_to_return = full_menu[cuisine.capitalize()]
        selected_cuisine_name = cuisine.capitalize()
    else:
        # If invalid cuisine, inform the user
        if cuisine:
             logger.warning(f"Requested cuisine '{cuisine}' not found.")
             return f"Sorry, we don't have a specific menu for {cuisine}. Available cuisines are: {', '.join(available_cuisines)}."
        # If no cuisine specified, default to Andhra Cafe
        logger.info("No specific cuisine requested, defaulting to Andhra Cafe.")
        menu_to_return = full_menu.get("Andhra Cafe", {}) # Use .get for safety
        selected_cuisine_name = "Andhra Cafe (Default)"


    # Apply dietary restrictions filter (improved example)
    filtered_menu = {}
    if dietary_restrictions and dietary_restrictions.lower() != "no restrictions" and menu_to_return: # Only filter if restrictions exist and we have a menu
        restriction = dietary_restrictions.lower()
        logger.info(f"Applying dietary restriction filter: '{restriction}'")
        for category, items in menu_to_return.items():
            filtered_items = []
            for item in items:
                # Simple check based on keywords in item description
                item_lower = item.lower()
                is_match = False

                # Handle specific restrictions
                if restriction == 'vegetarian' and '(vegetarian' in item_lower:
                    is_match = True
                elif restriction == 'vegan':
                     # Must explicitly say vegan or have a vegan option, and not contain dairy unless option specified
                    if ('(vegan' in item_lower) or \
                       ('(vegetarian' in item_lower and 'vegan option available' in item_lower and 'contains dairy' not in item_lower) or \
                       ('(vegetarian' in item_lower and 'vegan option available' in item_lower and 'contains dairy' in item_lower and 'vegan option available' in item_lower): # Handle cases like Semiya Payasam
                        is_match = True
                elif restriction == 'gluten-free':
                    # Must explicitly say gluten-free or have option, and not contain gluten
                    if ('(gluten-free' in item_lower or 'gluten-free option available' in item_lower) and 'contains gluten' not in item_lower:
                         is_match = True
                elif restriction == 'nut-free':
                    # Must NOT contain nuts unless specified otherwise (or if item naturally doesn't have nuts)
                    if 'contains nuts' not in item_lower:
                        is_match = True
                    elif 'specify nut-free' in item_lower: # Allow if modification is possible
                        item += " (Specify Nut-Free)" # Add note for user
                        is_match = True
                elif restriction == 'dairy-free':
                     # Must not contain dairy unless a vegan/dairy-free option is explicitly available
                    if 'contains dairy' not in item_lower:
                        is_match = True
                    elif 'vegan option available' in item_lower: # Vegan implies dairy-free
                         is_match = True
                elif restriction == 'halal' and '(halal' in item_lower:
                    is_match = True
                # Add more restriction checks here if needed

                # Include item if it matches the restriction
                if is_match:
                    filtered_items.append(item)
                # A more robust system would use explicit tags: item_tags = ['vegetarian', 'gluten-free', 'contains_nuts']

            if filtered_items: # Only add category if it has items after filtering
                filtered_menu[category] = filtered_items

        # If filtering resulted in an empty menu, report that
        if not filtered_menu and menu_to_return: # Check if original menu wasn't empty
            logger.warning(f"No items found matching '{dietary_restrictions}' on the {selected_cuisine_name} menu.")
            return f"Sorry, we couldn't find any items matching '{dietary_restrictions}' on the {selected_cuisine_name} menu."
        menu_to_return = filtered_menu # Use the filtered menu
    elif not menu_to_return:
         # This case handles if the initial cuisine lookup failed (e.g., default Andhra Cafe wasn't found)
         logger.error("Initial menu selection resulted in an empty menu.")
         return "Sorry, there seems to be an issue retrieving the menu right now."


    # --- Format Output ---
    if not menu_to_return:
         # This case might happen if the base cuisine menu was empty or filtering removed everything validly
         logger.warning(f"Menu for {selected_cuisine_name} is empty after processing.")
         return f"Sorry, I couldn't find menu items for {selected_cuisine_name} matching your request."


    output_string = f"Okay, here is the {selected_cuisine_name} menu"
    if dietary_restrictions and dietary_restrictions.lower() != "no restrictions":
        output_string += f" filtered for {dietary_restrictions}"
    output_string += ":\n"

    for category, items in menu_to_return.items():
        output_string += f"\n**{category}**\n"
        for item in items:
            output_string += f"- {item}\n"

    logger.info(f"getMenu result generated successfully.")
    return output_string.strip()