def place_order(items, order_type="dine-in", table_number=None):
    """
    Places a restaurant order.

    Args:
        items (list): A list of dictionaries, where each dict represents an item
                      (e.g., {"name": "Burger", "quantity": 1, "notes": "no onions"}).
        order_type (str): The type of order (e.g., "dine-in", "takeout", "delivery").
                          Defaults to "dine-in".
        table_number (str, optional): The table number for dine-in orders.

    Returns:
        dict: A dictionary containing the status and message, and potentially
              an order_id on success.
    """
    global mock_orders
    global order_id_counter

    if not items:
        return {"status": "error", "message": "Cannot place an empty order."}

    # --- Simulate order processing (no libraries) ---
    # Generate a simple mock order ID using the counter
    order_id_counter += 1
    order_id = f"MOCK-ORDER-{order_id_counter}"

    # Store the mock order with an initial status
    mock_orders[order_id] = {
        "items": items,
        "order_type": order_type,
        "table_number": table_number,
        "status": "received" # Initial status
    }

    response_message = f"Thank you! Your order has been placed. Your order ID is {order_id}."
    if order_type == "dine-in" and table_number:
         response_message += f" It will be delivered to table {table_number}."
    elif order_type == "takeout":
         response_message += " We will notify you when it's ready for pickup."
    # Add messages for other order types if needed

    return {
        "status": "success",
        "message": response_message,
        "order_id": order_id
    }