def check_order_status(order_id):
    """
    Checks the status of an order

    Args:
        order_id (str): The ID of the order to check.

    Returns:
        dict: A dictionary containing the status and a message describing the
              order status, or an error if the ID is not found.
    """
    global mock_orders

    order_info = mock_orders.get(order_id)

    if not order_info:
        return {"status": "error", "message": f"Order with ID {order_id} not found."}

    current_status = order_info["status"]
    # Creating items list manually without join from libraries
    items_list_parts = []
    for item in order_info['items']:
        items_list_parts.append(f"{item['quantity']} x {item['name']}")
    items_list = ", ".join(items_list_parts) # Still need join, let's avoid it...
    # Let's manually build the string without join too
    items_list = ""
    for i, item in enumerate(order_info['items']):
        items_list += f"{item['quantity']} x {item['name']}"
        if i < len(order_info['items']) - 1:
            items_list += ", "


    # Simulate status progression based on current status for the message
    # Note: The actual stored status in mock_orders is NOT changed by this function
    if current_status == "received":
        status_message = f"Your order ({items_list}) has been received and is being sent to the kitchen."
    elif current_status == "preparing":
        status_message = f"Your order ({items_list}) is currently being prepared in the kitchen."
    elif current_status == "ready":
        status_message = f"Good news! Your order ({items_list}) is ready for pickup/delivery."
    elif current_status == "completed":
        status_message = f"Your order ({items_list}) was completed."
    else:
        status_message = f"Your order ({items_list}) has an unknown status: {current_status}."


    return {
        "status": "success",
        "message": status_message,
        "order_status": current_status
    }