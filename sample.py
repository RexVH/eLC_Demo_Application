"""Explicitly synthetic fixtures; course names transcribed from the user's screenshot."""
from api import BASE, OPS, Result, parameters, request_path
from urllib.parse import urlencode

COURSES = [
    "ARTI9300 Doctoral Dissertation Fall 2026 67977",
    "AI Sandbox Course 2025",
    "UGA Data Science Competition 2021",
    "DAE at a Distance | An eLC Experience 3.0",
]


class SampleClient:
    mode = "Sample data"

    def close(self):
        pass

    def call(self, key, lp, le, course="", item="", bookmark=""):
        path = request_path(key, lp, le, course, item)
        query = parameters(key, bookmark)
        url = BASE + path + ("?" + urlencode(query) if query else "")
        toc = {"Modules": [{"ModuleId": 91001, "Title": "Start here", "Modules": [{"ModuleId": 91002, "Title": "Course documents", "Modules": [], "Topics": [{"TopicId": 92001, "Title": "Syllabus (synthetic example)", "Type": 1, "Url": "/sample/syllabus.txt"}]}], "Topics": [{"TopicId": 92002, "Title": "Welcome and course navigation", "Type": 1}]}]}
        enrollments = [{"OrgUnit": {"Id": 90001 + i, "Name": name, "Code": f"SAMPLE-{i+1}", "Type": {"Id": 3}}, "Access": {"CanAccess": True}} for i, name in enumerate(COURSES)]
        data = {
            "versions": [{"ProductCode": "lp", "Version": "1.49"}, {"ProductCode": "le", "Version": "1.82"}],
            "identity": {"Identifier": "sample-user", "DisplayName": "Sample presenter", "UniqueName": "sample"},
            "enrollments": {"Items": enrollments, "PagingInfo": {"HasMoreItems": False, "Bookmark": "90004"}},
            "enrollment": next((x for x in enrollments if str(x["OrgUnit"]["Id"]) == course), {}),
            "course": {"Identifier": course, "Name": next((x["OrgUnit"]["Name"] for x in enrollments if str(x["OrgUnit"]["Id"]) == course), "Synthetic course"), "IsActive": True},
            "toc": toc,
            "roots": [{"Id": 91001, "Title": "Start here", "Type": 0}],
            "module": [{"Id": 91002, "Title": "Course documents", "Type": 0}] if item == "91001" else [{"Id": 92001, "Title": "Syllabus (synthetic example)", "Type": 1}],
            "topic": {"Id": int(item) if item else 92001, "Title": "Syllabus (synthetic example)", "Type": 1, "Url": "/sample/syllabus.txt"},
            "overview": {"Description": {"Text": "Synthetic course overview. All IDs and course contents in sample mode are fictional.", "Html": None}},
            "news": [{"Id": 93001, "Title": "Welcome to the sample course", "Body": {"Text": "This is rehearsal content, not a live eLC announcement."}}],
            "assignments": [{"Id": 94001, "Name": "Sample project proposal", "DueDate": "2026-11-24T22:00:00Z"}],
            "quizzes": {"Objects": [{"QuizId": 95001, "Name": "Sample practice quiz"}], "Next": None},
            "calendar": [{"CalendarEventId": 96001, "Title": "Sample project proposal due", "StartDateTime": "2026-11-24T22:00:00Z", "EndDateTime": "2026-11-24T22:00:00Z"}],
        }
        if OPS[key].file:
            return Result(key, url, 200, 8, body=b"SYNTHETIC SYLLABUS - NOT LIVE eLC DATA\nUnit 1: Responsible AI and APIs\nRead: sample course notes\nProject proposal due: November 24, 2026, 5:00 PM America/New_York\nPolicy: verify all generated dates against the source.\n", mime="text/plain", filename="sample-syllabus.txt", sample=True)
        return Result(key, url, 200, 8, data=data[key], mime="application/json", sample=True)
