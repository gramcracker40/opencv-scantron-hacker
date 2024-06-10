import json
import base64
import io
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, APIRouter, Depends, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import cv2
from tables import Submission, Student, Test
from db import session
from models.submission import GetStudentSubmission, GetSubmission, UpdateSubmission
from answer_sheets.grader import OMRGrader
from routers.auth import get_current_user

router = APIRouter(
    prefix="/submission",
    tags=["submission"],
    responses={404: {"description": "Not found"}},
    redirect_slashes=True
)

@router.post("/")
async def create_submission_live(
    submission_image: UploadFile,
    student_id: int = Form(...),
    test_id: str = Form(...), 
    mechanical: bool = False
):
    try:
        print("Received request to create submission")
        # query student and test to make sure they exist
        student = session.query(Student).get(student_id)
        test = session.query(Test).get(test_id)
        
        if student is None:
            raise HTTPException(404, detail="Student not found")

        if test is None:
            raise HTTPException(404, detail="Test not found")

        # load key needed to grade submission
        test_key = json.loads(test.answers)

        # grab the bytes of whatever image was submitted
        image_data = await submission_image.read()

        print(f"{test.name} Key: {test_key}")
        print(f"image_name: {submission_image.filename}")
        print(f"image_data: {image_data[0:10]}")

        print("here 1")
        # grade the submission
        grader = OMRGrader(
            num_choices=test.num_choices, 
            num_questions=test.num_questions, 
            font_path="answer_sheets/assets/fonts/RobotoMono-Regular.ttf",
            mechanical=mechanical
        )
        print("here 2")

        grade, graded, choices = grader.run(bytes_obj=image_data, key=test_key)
        graded_image_bytes = OMRGrader.convert_image_to_bytes(grader.image)
        print(f"grade: {grade}\ngraded: {graded}\nchoices: {len(choices)}")
        print("here 3")

        new_submission = Submission(
            submission_image=image_data,
            graded_image=graded_image_bytes, 
            answers=json.dumps({
                question_num: (choices[question_num][2], graded[question_num])
                for question_num in graded
            }), # {1: ("A", True), 2: ("F", False)}  -->  answers (JSON str)
            grade=grade,
            student_id=student_id,
            test_id=test.id
        )
        print("here 4")

        print(f"NEW SUBMISSION: {new_submission}")
        print("here 5")

        session.add(new_submission)
        session.commit()
        print("here 6")

        return {"success": True, "submission_id": new_submission.id}
    
    except SQLAlchemyError as e:
        print(f"Database error: {e}")
        session.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred")
    
    except Exception as e:
        print(f"Unhandled error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred")

@router.delete("/{submission_id}")
def delete_submission(submission_id: int):
    submission = session.query(Submission).get(submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    session.delete(submission)
    session.commit()

    return {"detail": "successfully deleted submission"}


@router.get("/{submission_id}", response_model=GetSubmission)
def get_submission(submission_id: int):
    submission = session.query(Submission).get(submission_id)
    
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    student = session.query(Student).get(submission.student_id)
    sub = {
        'student_name': student.name, 
        'student_id': submission.student_id, 
        'grade': submission.grade, 
        'id': submission_id
    }
    
    return sub


@router.get("/test/{test_id}", response_model=List[GetSubmission])
def get_submissions_for_test(test_id: str):
    test = session.query(Test).get(test_id)

    if test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    submissions = [
        {
            'id': sub.id,
            'student_id': sub.student.id,
            'student_name': sub.student.name,
            'grade': sub.grade            
        } 
        for sub in test.submissions
    ]
    
    return submissions


@router.get("/image/graded/{submission_id}")
def get_submission_graded_image(submission_id: int):
    submission = session.query(Submission).get(submission_id)

    if not submission:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return StreamingResponse(io.BytesIO(submission.graded_image), media_type="image/png")


@router.get("/image/original/{submission_id}")
def get_submission_original_image(submission_id: int):
    submission = session.query(Submission).get(submission_id)

    if not submission:
        raise HTTPException(status_code=404, detail="Test not found")
    
    return StreamingResponse(io.BytesIO(submission.submission_image), media_type="image/png")



@router.get("/student/{student_id}", response_model=List[GetStudentSubmission])
def get_submissions_for_student(student_id: int):
    student = session.query(Student).get(student_id)

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    return student.submissions


@router.get("/student/{student_id}/{course_id}", response_model=List[GetStudentSubmission])
def get_submissions_for_student_for_course(student_id: int, course_id:int):

    submissions = session.query(Submission).filter(
        Submission.student_id == student_id
    ).all()

    submissions = [x for x in submissions if x.test.course_id == course_id]

    print(f"submissions: {submissions}")

    if not submissions:
        raise HTTPException(status_code=404, detail="No submissions found for this student in this course.")

    print(f"submissions: {submissions}")

    return submissions


@router.get("/{test_id}/{student_id}", response_model=GetSubmission)
def get_submission_for_test_for_student(test_id:str, student_id:int):
    test_sub = session.query(Submission).filter(
        Submission.student_id==student_id, 
        Submission.test_id==test_id
    ).first()

    if test_sub is None:
        raise HTTPException(404, detail=f"submission with this student and test id not found!")


    return {
        'id': test_sub.id,
        'student_id': test_sub.student_id,
        'student_name': test_sub.student.name,
        'grade': test_sub.grade
    }



# @router.post("/882E")
# def create_submission_882E(submission: CreateSubmission):
#     '''
#     Create a submission using a Form 882E
#     '''
#     # query student and test, ensure request validity
#     student = session.query(Student).get(submission.student_id)
#     test = session.query(Test).get(submission.test_id)

#     if not student:
#         raise HTTPException(404, detail=f"student {submission.student_id} does not exist")
#     if not test:
#         raise HTTPException(404, detail=f"test {submission.test_id} does not exist")

#     try: 
#         # turn base64 string into bytes obj
#         submission_image = base64.b64decode(submission.submission_photo.encode("utf-8"))
#         test_key = json.loads(test.answers)
#         test_key = {int(x): test_key[x] for x in test_key}
#         print("test_key", json.dumps(test_key))
#         # create ScantronProcessor for handling submission 
#         # new_submission = ScantronProcessor(
#         #     test_key, 
#         #     image=submission_image 
#         # )
#         # process the submission, obtaining user answers and grade
#         # graded_answers, grade = new_submission.process()
#         # # convert Matlike obj to bytes obj for storage in db
#         # image_buffer = cv2.imencode('.jpg', new_submission.image)[1]
#         # graded_image = image_buffer.tobytes()

#         # instantiate new submission obj
#         db_submission = Submission(
#             # graded_photo=graded_image, 
#             file_extension='jpg', 
#             num_questions=test.num_questions, 
#             # answers=json.dumps(graded_answers), 
#             # grade=grade, 
#             student_id=student.id, 
#             test_id=test.id
#         )
#         session.add(db_submission)
#         session.commit()
        
#         return {"detail": f"successfully submitted the answer key for {test.name}"}
#     except IntegrityError:
#         raise HTTPException(400, detail="Student has already submitted to this test")
#     except cv2.error as e:
#         print(str(e))
#         print("CV2 Error!!!")
#         session.rollback()
#         raise HTTPException(400, detail="Submission could not be processed, please try again.")
