import json
import base64
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, APIRouter
from pydantic import BaseModel
import cv2
from tables import Submission, Student, Test
from db import session
from models.submission import CreateSubmission, GetSubmission, UpdateSubmission
from core.ScantronProcessor import ScantronProcessor

router = APIRouter(
    prefix="/submission",
    tags=["submission"],
    responses={404: {"description": "Not found"}},
    redirect_slashes=True
)

@router.post("/")
def create_submission(submission: CreateSubmission):
    # query student and test, ensure request validity
    student = session.query(Student).get(submission.student_id)
    test = session.query(Test).get(submission.test_id)

    if not student:
        raise HTTPException(404, detail=f"student {submission.student_id} does not exist")
    if not test:
        raise HTTPException(404, detail=f"test {submission.test_id} does not exist")

    try: 
        # turn base64 string into bytes obj
        submission_image = base64.b64decode(submission.submission_photo.encode("utf-8"))
        test_key = json.loads(test.answers)
        test_key = {int(x): test_key[x] for x in test_key}
        print("test_key", json.dumps(test_key))
        # create ScantronProcessor for handling submission 
        new_submission = ScantronProcessor(
            test_key, 
            image=submission_image 
        )
        # process the submission, obtaining user answers and grade
        graded_answers, grade = new_submission.process()
        # convert Matlike obj to bytes obj for storage in db
        image_buffer = cv2.imencode('.jpg', new_submission.image)[1]
        graded_image = image_buffer.tobytes()

        # instantiate new submission obj
        db_submission = Submission(
            graded_photo=graded_image, 
            file_extension='jpg', 
            num_questions=test.num_questions, 
            answers=json.dumps(graded_answers), 
            grade=grade, 
            student_id=student.id, 
            test_id=test.id
        )
        session.add(db_submission)
        session.commit()
        
        return {"detail": "successfully submitted the answer key for "}
    except IntegrityError:
        raise HTTPException(400, detail="Student has already submitted to this test")
    except cv2.error as e:
        print(str(e))
        print("CV2 Error!!!")
        session.rollback()
        raise HTTPException(400, detail="Submission could not be processed, please try again.")


@router.get("/{submission_id}", response_model=GetSubmission)
def get_submission(submission_id: int):
    submission = session.query(Submission).get(submission_id)
    
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission



@router.delete("/{Submission_id}", response_model=GetSubmission)
def delete_submission(Submission_id: int):
    db = session()
    db_Submission = db.query(Submission).filter(Submission.id == Submission_id).first()
    if db_Submission is None:
        db.close()
        raise HTTPException(status_code=404, detail="Submission not found")
    db.delete(db_Submission)
    db.commit()
    db.close()
    return db_Submission