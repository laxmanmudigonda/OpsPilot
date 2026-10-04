from fastapi import FastAPI, Response, status

app = FastAPI(title="OpsPilot Demo Service")
state = {"failed": False}


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    if state["failed"]:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"status": "down"}
    return {"status": "healthy"}


@app.post("/fail")
def fail() -> dict[str, str]:
    state["failed"] = True
    return {"status": "failure enabled"}


@app.post("/recover")
def recover() -> dict[str, str]:
    state["failed"] = False
    return {"status": "recovered"}
