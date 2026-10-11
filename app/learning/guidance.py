"""Prompts shown for each action tag (PLAN.md 7.3).

These are help for the learner. They never add a requirement that the
requirement text does not contain. Edit the wording here.
"""

GENERIC = "Do what the requirement text asks, then record what you did."

BY_TAG = {
    "demonstrate": (
        "Do the skill for real, then add a photo, video, audio, file, or a witness record. "
        "A text answer alone is not a demonstration. Reading about it or watching a video is "
        "preparation, not a demonstration."
    ),
    "show": (
        "Show it for real, then add a photo, video, audio, file, or a witness record. "
        "A text answer alone does not show the skill."
    ),
    "discuss": (
        "Have the discussion. Record who took part and what you talked about. If the "
        "requirement names a person, that person must be a real human. Practice with an AI "
        "does not replace the required conversation."
    ),
    "explain": (
        "Write your explanation in your own words. Copied or generated text does not show "
        "that you understand it."
    ),
    "describe": "Describe it in your own words and save your answer as a note or text response.",
    "read": (
        "Read what the requirement names. A summary does not replace the reading. "
        "Use a note to log what you read and when."
    ),
    "interview": (
        "Interview a real person. Record the date, their role, your questions or notes, and "
        "what you learned. An AI chat is not an interview. Do not record an interview that "
        "did not happen."
    ),
    "log": (
        "Add a dated entry each time. Each entry has a date and the minutes you spent. "
        "Check the requirement text for how many entries or how much time it asks for."
    ),
    "teach": (
        "Teach another person. Add a lesson plan, and evidence that you taught it, such as a "
        "witness record or a photo. A plan alone is not teaching."
    ),
    "make": "Make the item. Add photos or files of it, or log the time you spent.",
    "build": "Build the item. Add photos or files of it, or log the time you spent.",
    "conduct": "Carry out the activity. Record what you did, when, and who took part.",
    "participate": "Take part in the activity. Record when, where, and what you did.",
    "visit": "Go to the place. Record the date, where you went, and what you saw.",
    "plan": "Write your plan and save it as a text response. A plan is not the activity itself.",
    "prepare": "Do the preparation the text asks for, and record what you prepared.",
    "research": "Record what you found and where you found it. Link your sources.",
    "reflect": "Write your own reflection as a text response.",
}


def guidance_for(tags):
    """List of (tag, text) for the node's tags. A generic line if there are none."""
    out = [(t, BY_TAG.get(t, GENERIC)) for t in tags]
    return out or [("", GENERIC)]
