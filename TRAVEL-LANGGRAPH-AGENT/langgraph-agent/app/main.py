from fastapi import FastAPI, Body, HTTPException
from app.graph import graph
from app.config import logger
from langgraph.types import Command
app = FastAPI(title="Travel Agent API")

@app.post("/chat")
async def chat(payload: dict = Body(...)):
    thread_id = payload.get("thread_id", "session_1")
    config = {"configurable": {"thread_id": thread_id}}
    action = payload.get("action")
    data = payload.get("data", {})

    try:
        if action == "start":
            graph.invoke(data, config)
        
        elif action == "select_prices":
            # 1. Update the state with the user's choice
            graph.update_state(config, data)
            graph.invoke(None, config)
            # # 2. IMPORTANT: Check if we already have both flight AND hotel
            # state_now = graph.get_state(config).values
            # if state_now.get("selected_flight_price") and state_now.get("selected_hotel_price"):
            #     # Run the graph to process budget_check and activities
            #     # It will automatically stop at 'booking_node' because of the interrupt
            #     graph.invoke(None, config)
            # else:
            #     # If we're still missing one, just run to the next selection point
            #     graph.invoke(None, config)

        elif action == "confirm_booking":
            graph.invoke(
                Command(resume={"approved": True}),
                config
            )

        elif action == "retrieve":
            pass 

        elif action == "fix_budget":
            # Update total_budget and re-run supervisor/route logic
            graph.update_state(config, data)
            graph.invoke(None, config)
            
        else:
            raise HTTPException(status_code=400, detail="Invalid action")

        # Get the latest values from the checkpointer
        state_values = graph.get_state(config).values
        return state_values

    except Exception as e:
        logger.error(f"Backend Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "healthy"}