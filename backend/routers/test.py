from fastapi import HTTPException, APIRouter
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from models.test import CreateTest, UpdateTest, GetTest, CreateTestConfirmation
from tables import Test, Course
from db import get_db, session
import base64
from time import sleep
from core.TestProcessor import TestProcessor

router = APIRouter(
    prefix="/test",
    tags=["test"],
    responses={404: {"description": "Test: Not found"}},
    redirect_slashes=True,
)


@router.post(
    "/", response_model=CreateTestConfirmation
)  # , #dependencies=[Depends(jwt_token_verification)])
def create_test(test: CreateTest):
    try:
        answer_key = base64.b64decode(test.answer_key.encode("utf-8"))



        temp = Test(
            name=test.name,
            start_t=test.start_t,
            end_t=test.end_t,
            num_questions=test.num_questions,
            answer_key=answer_key,
            course_id=test.course_id,
            file_extension=test.file_extension
            
        )
        session.add(temp)
        session.commit()
    except IntegrityError as e:
        print(f"Error create-test: {e}")
        session.rollback()
        raise HTTPException(status_code=400, detail="This test already exists")

    new_test = session.query(Test).filter(
        Test.name == test.name, Test.course_id == test.course_id
    ).first()

    return {"id": new_test.id, "name": new_test.name}


@router.get("/", response_model=List[GetTest])
def get_all_tests():
    tests = session.query(Test).all()
    if len(tests) == 0:
        return []
    print(f"Tests: {tests}")
    # returnable = [test for test in tests]
    try:
        print(f"answer_key: {type(tests[0].answer_key)}")
        for test in tests:
            test.answer_key = base64.b64encode(test.answer_key).decode("utf8")
        print(f"answer_key: {type(tests[0].answer_key)}")

        #sleep(8)
        return tests

    except EncodingWarning:
        raise HTTPException(500, detail="Binary decoding warning...")
    finally:
        session.rollback()


@router.get("/{test_id}/", response_model=GetTest)
def get_test_by_id(test_id: int, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    return test


@router.put("/{test_id}/")
def update_test(test_id: int, update_data: UpdateTest, db: Session = Depends(get_db)):
    test = db.query(Test).filter(Test.id == test_id).first()

    # make sure it found one
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    test.start_t = update_data.start_t
    test.end_t = update_data.end_t
    test.num_questions = update_data.num_questions
    test.answer_key = update_data.answer_key

    db.commit()

    return test


@router.delete("/{test_id}/")
def delete_test(test_id: int):
    test = session.query(Test).get(test_id)
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    session.delete(test)
    session.commit()

    return {"message": "Test deleted successfully"}
