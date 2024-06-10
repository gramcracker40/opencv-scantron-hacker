import cv2
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os

class DocumentExtractionFailedError(Exception):
    """
    Exception raised for errors in the Scantron extraction process.
    """
    def __init__(self, 
        message="""Scantron extraction failed, 
please check the background and ensure 
there is a consistent background"""):
        self.message = message
        super().__init__(self.message)


def show_image(title: str, matlike: cv2.Mat_TYPE_MASK, w=600, h=700):
    """
    given a title and Matlike image, display it given configured width and height
    """

    temp = cv2.resize(matlike, (w, h))
    cv2.imshow(title, temp)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def pre_process(image):
    '''
    prepares the image for finding contours. 
    '''
    image = equalize_histogram(image) # levels out inconsistent brightness
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    edges = cv2.Canny(thresh, 50, 150)
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    return dilated


def order_points(pts):
    # Order points in the order: top-left, top-right, bottom-right, bottom-left
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]

    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def equalize_histogram(image):
    """
    Applies adaptive histogram equalization to the input image to improve contrast.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    equalized = clahe.apply(gray)
    return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)


def four_point_transform(image, pts):
    rect = order_points(pts)
    (tl, tr, br, bl) = rect

    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))

    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight), borderMode=cv2.BORDER_REPLICATE)
    show_image("warped", warped)
    return warped


class OMRGrader:
    '''
    Handles all functionality surrounding grading LiveTest answer sheet documents
    
    can grade mechanically produced selected answers on LiveTest's answer_sheets module. 
        examples: ./generatedSheets

    can grade pictures taken of answer sheets filled out by hand as well. 
        examples: ./submissionSheets
        - handles all pre processing
        - handles four point transformation
        - returns Matlike obj of isolated answer sheets post four point transformation.
    
    '''
    def __init__(self, num_choices, num_questions, mechanical:bool=True, 
                 font_path:str="assets/fonts/RobotoMono-Regular.ttf", font_size:int=180):
        self.font_path = font_path
        self.font_size = font_size
        self.num_choices = num_choices
        self.num_questions = num_questions
        self.mechanical = mechanical

    @classmethod
    def convert_image_to_bytes(self, image: np.ndarray) -> bytes:
        if image is not None and image.size > 0:
            success, encoded_image = cv2.imencode('.png', image)
            if success:
                return encoded_image.tobytes()
        return None
    
    def show_image(self, title: str, matlike, w=600, h=700):
        temp = cv2.resize(matlike, (w, h))
        cv2.imshow(title, temp)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    def is_circle(self, contour, threshold=0.9):
        '''
        given a contour determine if it is a circle
        '''
        area = cv2.contourArea(contour)
        
        # bounding circle
        (x, y), radius = cv2.minEnclosingCircle(contour)
        circle_area = np.pi * (radius ** 2)
        
        # circularity ratio
        circularity = area / circle_area
        
        # return if the contour is a circle
        return circularity > threshold
    

    def isolate_document(self, image_path:str=None, image_bytes:bytes=None):
        if image_path is not None:
            image = cv2.imread(image_path)
            print("Image loaded from path.")
        elif image_bytes is not None:
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            print("Image decoded from bytes.")
        else:
            raise DocumentExtractionFailedError("Must provide a valid image")
        self.image = image
        show_image("prepre_process(image)", image)
        image_proc = pre_process(image)
        show_image("pre_process(image)", image_proc)
        contours, _ = cv2.findContours(image_proc, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:3]
        print(f"Found {len(contours)} contours.")

        #cv2.drawContours(image, contours, -1, (0,255,255), 111)
        show_image("drawContours(image)", image)

        # Loop over the contours
        for i, c in enumerate(contours):
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.025 * peri, True)
            print(f"Contour #{i + 1}: {len(approx)} vertices.")

            if len(approx) == 4:
                print("Document found. Performing transformation.")
                transformed = four_point_transform(image, approx.reshape(4, 2))
                show_image("transformed!", transformed)
                return transformed

        raise DocumentExtractionFailedError("Document could not be isolated")


    def get_answer_bubbles(self, file_path:str=None, bytes_obj:bytes=None):
        if file_path is not None:
            print("file path ran")
            self.image = cv2.imread(file_path)
        elif bytes_obj is not None:
            print("bytes obj eing used")
            nparr = np.frombuffer(bytes_obj, np.uint8)
            self.image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            print("loaded image!")
        else:
            if not len(self.image) > 0:
                raise ValueError("Either file_path or bytes_obj must be provided.")
        
        if self.image is None:
            raise ValueError("The image could not be loaded. Check the input data.")
        show_image("starting answer_bubbles", self.image)
        print("starting bubbles")
        if len(self.image.shape) == 3: # rectangle
            gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
            #blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            self.thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            print("thresholded image!")
        self.show_image("Thresholded image", self.thresh)

        contours, _ = cv2.findContours(self.thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        question_contours = []
        print(f"contours: {len(contours)}")
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)
            if self.is_circle(contour) and 0.9 <= aspect_ratio <= 1.1:
                question_contours.append(contour)
                #cv2.drawContours(self.image, [contour], -1, (0,255,0), 2) # debugging

        self.show_image("contours highlighted", self.image)
        print(f"#question choices: {len(question_contours)}")

        return question_contours, self.image


    def sort_contours(self, cnts, method="left-to-right"):
        reverse = method in ["right-to-left", "bottom-to-top"]
        i = 1 if method in ["top-to-bottom", "bottom-to-top"] else 0
        bounding_boxes = [cv2.boundingRect(c) for c in cnts]
        sorted_cnts = sorted(zip(cnts, bounding_boxes), key=lambda b: b[1][i], reverse=reverse)
        return zip(*sorted_cnts)


    def group_bubbles_by_row(self, cnts):
        cnts, bounding_boxes = self.sort_contours(cnts, "top-to-bottom")
        rows = []
        current_row = []
        row_y = bounding_boxes[0][1]

        for contour, box in zip(cnts, bounding_boxes):
            if abs(box[1] - row_y) < 30:
                current_row.append(contour)
            else:
                if current_row:
                    current_row, _ = self.sort_contours(current_row, "left-to-right")
                    rows.append(current_row)
                current_row = [contour]
                row_y = box[1]
        
        if current_row:
            current_row, _ = self.sort_contours(current_row, "left-to-right")
            rows.append(current_row)

        return rows


    def sort_rows_to_questions(self, rows):
        questions = {}
        col_num = 0
        i = 0
        print(f"#ROWS: {len(rows)}, type(row): {type(rows[0])}")
        while i < self.num_questions:
            questions[i + 1] = [
                rows[i % len(rows)][choice]
                for choice in range(col_num, col_num + self.num_choices)
            ]
            i += 1
            if i % len(rows) == 0:
                col_num += self.num_choices

        return questions
    
    
    def identify_question_choices(self, questions:dict):
        '''
        questions: 
        {
            1: [[cntCoordinatesA], [cntCoordinatesB]], 
            2: [[cntCoordinatesA], [cntCoordinatesB]]
        }

        Description: given a dictionary of questions from sortRowsToQuestions, return a 
        dictionary with the same keys but the contour that is the marked answer
        as the value

        How it works: counting the number of non-zero pixels (foreground pixels) in each bubble region
                        this function determines which bubble was circled in out of the number of choices. 

        returns --> answer-sheets recorded results. 
        {}
        '''
        choices = {}
        for question, contours in questions.items():
            for j, c in enumerate(contours):
                print(f"Choice {j + 1} of question {question}: Type: {type(c)}, Shape: {c.shape}")

                mask = np.zeros_like(self.thresh, dtype="uint8")
                try:
                    cv2.drawContours(mask, [c], -1, 255, -1) 
                except cv2.error as e:
                    print(f"Error drawing contour {j} in question {question}: {e}")
                    continue 

                # apply the mask to the thresholded image, then count the number of non-zero pixels in the bubble area
                mask = cv2.bitwise_and(self.thresh, self.thresh, mask=mask)
                total = cv2.countNonZero(mask)
                print(f"#Non zero pixels: {total}")

                if question not in choices or total > choices[question][0]:
                    choices[question] = (total, c, chr(j + 65))  # store the choice with the highest total

        return choices
    

    def grade_choices(self, choices:dict, key:dict, outline_thickness:int=10):
        '''
        given a key and a dict of choices { 1: (_, contour, 'B'), 2: (_, contour, 'E') } 
        return the grade for the answer sheet, as well as mark whether or not they got it right
        and return the graded version
        '''
        graded = {}
        correct = 0

        for question_num in choices:
            if choices[question_num][2] == key[str(question_num)]:
                graded[question_num] = True
                # draw green outline
                cv2.drawContours(self.image, [choices[question_num][1]], -1, (0, 255, 0), outline_thickness)
                correct += 1
            else:
                graded[question_num] = False
                # draw red outline
                cv2.drawContours(self.image, [choices[question_num][1]], -1, (0, 0, 255), outline_thickness)

        return graded, correct/len(choices) * 100


    def add_grade(self, image, grade, 
                  position:tuple=(3050, 30), 
                  color=(0, 0, 0), 
                  output_size=(1920, 1080)):
        '''
        add the grade to the top right of the graded answer sheet. 
        '''
        
        # convert Matlike to RGB
        cv_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # convert the OpenCV image to a PIL image
        pil_image = Image.fromarray(cv_image)
        pil_image.resize(output_size)

        # draw grade on PIL image
        draw = ImageDraw.Draw(pil_image)
        font = ImageFont.truetype(self.font_path, self.font_size)
        draw.text(
            xy=position,
            text=f"{grade}%", 
            font=font, 
            fill=color,
        )

        # convert back to OpenCV image
        cv_image_final = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

        return cv_image_final


    def run(self, file_path:str=None, bytes_obj:bytes=None, key:dict=None):
        '''
        helper function to execute the full functionality of the OMRGrader class in LiveTest
        uses configurations set in the constructor to grade the answer sheet. 

        returns:
            grade: int --> ex: 96 or 73
            graded: dict --> {1: False, 2: False, 3: True}
            choices: dict --> {1: (_, contour, chr(j + 65))}
        '''
        # determine if the run is on a mechanical or a real life image of a submission. 
        if not self.mechanical: # run the pre-processing method
            self.image = self.isolate_document(file_path, bytes_obj)
            bubbles, image = self.get_answer_bubbles()
        else:
            bubbles, image = self.get_answer_bubbles(file_path, bytes_obj)
        # print("got bubbles")
        sorted_rows = self.group_bubbles_by_row(bubbles)
        # print("sorted_rows")
        questions = self.sort_rows_to_questions(sorted_rows)
        # print("questions")
        choices = self.identify_question_choices(questions)
        # print("choices")

        # for question in choices:
        #     print(f"Question: {question}, Answer: {choices[question][2]}")

        graded, grade = self.grade_choices(choices, key)

        # print(f"GRADE: {grade}\nGRADED: {graded}")

        grade_color = (255, 0, 0) if grade < 70 \
                else (0, 255, 0) if grade >= 85 \
                else (0, 255, 255) # yellow 70-84

        # add the grade to the image
        image = self.add_grade(image, grade, color=grade_color)
        
        self.show_image("Questions Highlighted", 
                        image, w=1500, h=1200)
        
        return grade, graded, choices

# usage
if __name__ == "__main__":
    num_choices = 4
    num_questions = 100

    grader = OMRGrader(
        num_choices=num_choices, 
        num_questions=num_questions, 
        mechanical=False
    )
    # print(os.getcwd())
    # f'generatedSheets/fakeTest{num_questions}-{num_choices}/submission-2.png'

    grade, graded, choices = grader.run(
        file_path=f"submissionSheets/100-4/IMG_9348.png", 
        key = { 
            '1': 'A',
            '2': 'B',
            '3': 'C',
            '4': 'D',
            '5': 'A',
            '6': 'B',
            '7': 'C',
            '8': 'D',
            '9': 'A',
            '10': 'B',
            '11': 'C',
            '12': 'D',
            '13': 'A',
            '14': 'B',
            '15': 'C',
            '16': 'D',
            '17': 'A',
            '18': 'B',
            '19': 'C',
            '20': 'D',
            '21': 'A',
            '22': 'B',
            '23': 'C',
            '24': 'D',
            '25': 'A',
            '26': 'B',
            '27': 'C',
            '28': 'D',
            '29': 'A',
            '30': 'B',
            '31': 'C',
            '32': 'D',
            '33': 'A',
            '34': 'B',
            '35': 'C',
            '36': 'D',
            '37': 'A',
            '38': 'B',
            '39': 'C',
            '40': 'D',
            '41': 'A',
            '42': 'B',
            '43': 'C',
            '44': 'D',
            '45': 'A',
            '46': 'B',
            '47': 'C',
            '48': 'D',
            '49': 'A',
            '50': 'B',
            '51': 'C',
            '52': 'D',
            '53': 'A',
            '54': 'B',
            '55': 'C',
            '56': 'D',
            '57': 'A',
            '58': 'B',
            '59': 'C',
            '60': 'D',
            '61': 'A',
            '62': 'B',
            '63': 'C',
            '64': 'D',
            '65': 'A',
            '66': 'B',
            '67': 'C',
            '68': 'D',
            '69': 'A',
            '70': 'B',
            '71': 'C',
            '72': 'D',
            '73': 'A',
            '74': 'B',
            '75': 'C',
            '76': 'D',
            '77': 'A',
            '78': 'B',
            '79': 'C',
            '80': 'D',
            '81': 'A',
            '82': 'B',
            '83': 'C',
            '84': 'D',
            '85': 'A',
            '86': 'B',
            '87': 'C',
            '88': 'D',
            '89': 'A',
            '90': 'B',
            '91': 'C',
            '92': 'D',
            '93': 'A',
            '94': 'B',
            '95': 'C',
            '96': 'D',
            '97': 'A',
            '98': 'B',
            '99': 'C',
            '100': 'D'
        }    
    )
    print(f"grade: {grade}\ngraded: {graded}\nchoices: {len(choices)}")
