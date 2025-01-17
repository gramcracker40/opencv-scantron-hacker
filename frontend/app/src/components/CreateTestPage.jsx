import React, { useEffect, useState, useContext } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { BackButton } from './BackButton';
import { EasyRequest, instanceURL, defHeaders } from '../api/helpers';
import { AuthContext } from '../context/auth.jsx';

export const CreateTestPage = () => {
  const [testDetails, setTestDetails] = useState({
    name: '',
    startTime: '',
    endTime: '',
    numberOfQuestions: '',
    numberOfChoices: '', 
    answerKey: {},
    courseId: ''
  });
  const [templateImage, setTemplateImage] = useState(null);
  const [visibleQuestions, setVisibleQuestions] = useState(10);

  const { authDetails } = useContext(AuthContext);
  const navigate = useNavigate();
  const location = useLocation();
  const { courseId } = location.state || {};

  useEffect(() => {
    if (courseId) {
      setTestDetails(prev => ({ ...prev, courseId }));
    } else {
      alert("No courseId provided, redirecting to courses page");
      navigate("/courses");
    }
  }, [courseId, navigate]);

  useEffect(() => {
    if (testDetails.numberOfQuestions && testDetails.numberOfChoices) {
      let newAnswerKey = {};
      for (let i = 1; i <= parseInt(testDetails.numberOfQuestions); i++) {
        newAnswerKey[i] = '';
      }
      setTestDetails(prev => ({ ...prev, answerKey: newAnswerKey }));
      fetchTestTemplate(testDetails);
    }
  }, [testDetails.numberOfQuestions, testDetails.numberOfChoices]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    let newValue = value;

    if (name === 'numberOfQuestions') {
      newValue = Math.max(1, Math.min(200, Number(value)));
      setVisibleQuestions(10);  // Reset visible questions when the number changes
    }
    setTestDetails({ ...testDetails, [name]: newValue });
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!testDetails.name || !testDetails.startTime || !testDetails.endTime ||
        !testDetails.numberOfQuestions || !testDetails.numberOfChoices || !testDetails.courseId) {
      alert("All fields are required. Please ensure all fields are filled.");
      return;
    }

    if (new Date(testDetails.endTime) <= new Date(testDetails.startTime)) {
      alert("End time must be after start time.");
      return;
    }

    const numQuestions = parseInt(testDetails.numberOfQuestions);
    const numChoices = parseInt(testDetails.numberOfChoices);

    if (numQuestions < 1 || numQuestions > 200) {
      alert("Number of questions must be between 1 and 200.");
      return;
    }

    if (numChoices < 2 || numChoices > 7) {
      alert("Number of choices must be between 2 and 7.");
      return;
    }

    for (let i = 1; i <= numQuestions; i++) {
      if (!testDetails.answerKey[i] || testDetails.answerKey[i].trim() === '') {
        alert(`Please provide an answer for question ${i}.`);
        return;
      }
    }

    createTest();
  };

  const handleScroll = (e) => {
    const { scrollTop, clientHeight, scrollHeight } = e.currentTarget;
    if (scrollHeight - scrollTop === clientHeight) {
      setVisibleQuestions((prevVisibleQuestions) => Math.min(prevVisibleQuestions + 10, parseInt(testDetails.numberOfQuestions)));
    }
  };

  const createTest = async () => {
    const body = {
      "name": testDetails.name,
      "start_t": testDetails.startTime,
      "end_t": testDetails.endTime,
      "num_questions": testDetails.numberOfQuestions,
      "num_choices": testDetails.numberOfChoices,
      "course_id": testDetails.courseId,
      "answers": testDetails.answerKey
    };

    try {
      let req = await EasyRequest(instanceURL + "/test/", defHeaders, "POST", body);
      if (req.status === 200) {
        navigate(`/course/${testDetails.courseId}`);
      } else if (req.status === 409) {
        alert('This same exact test already exists. Please name it differently.');
      }
    } catch (error) {
      console.error('Error creating test', error);
      alert('An error occurred while creating the test.');
    }
  };

  const fetchTestTemplate = async (tempData) => {
    const url = `${instanceURL}/test/image/blank/${tempData.numberOfQuestions}/${tempData.numberOfChoices}/${encodeURIComponent(testDetails.courseId)}?test_name=${encodeURIComponent(tempData.name)}`;

    try {
      const response = await fetch(url, { method: 'GET' });
      if (!response.ok) {
        throw new Error(`Failed to fetch the image: ${response.statusText}`);
      }
      const imageBlob = await response.blob();
      const imageObjectURL = await URL.createObjectURL(imageBlob);
      setTemplateImage(imageObjectURL);
    } catch (error) {
      console.error('Error fetching test template', error);
    }
  };

  const handleAnswerChange = (questionNumber, choice) => {
    const newAnswerKey = {
      ...testDetails.answerKey,
      [questionNumber]: choice
    };
    setTestDetails({ ...testDetails, answerKey: newAnswerKey });
  };

  const generateAnswerInputs = () => {
    let inputs = [];
    const numQuestions = parseInt(testDetails.numberOfQuestions);
    const numChoices = parseInt(testDetails.numberOfChoices);

    if (!Number.isInteger(numQuestions) || numQuestions < 1 || !Number.isInteger(numChoices) || numChoices < 1) {
      return <div>Please enter valid numbers for questions and choices.</div>;
    }

    const limit = Math.min(numQuestions, visibleQuestions);

    for (let i = 1; i <= limit; i++) {
      inputs.push(
        <div key={i} style={{ marginBottom: '20px' }}>
          <div>#{i}:</div>
          <div style={{ display: 'flex', justifyContent: 'space-around' }}>
            {[...Array(numChoices).keys()].map(choice => (
              <div
                key={choice}
                style={{
                  width: '30px',
                  height: '30px',
                  borderRadius: '50%',
                  backgroundColor: testDetails.answerKey[i] === String.fromCharCode(65 + choice) ? 'lightblue' : 'gray',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: 'white'
                }}
                onClick={() => handleAnswerChange(i, String.fromCharCode(65 + choice))}
              >
                {String.fromCharCode(65 + choice)}
              </div>
            ))}
          </div>
        </div>
      );
    }
    return inputs;
  };

  return (
    <div className="bg-LogoBg min-h-screen w-full flex flex-col justify-center px-6 py-12 lg:px-8">
      <div className="absolute top-4 left-4">
        <BackButton className="px-8 py-3 text-sm font-semibold rounded-md shadow-sm bg-cyan-200 text-gray-700 hover:bg-cyan-300" />
      </div>
      <div className="overflow-y-auto sm:mx-auto sm:w-full sm:max-w-md h-full">
        <h1 className="text-center text-6xl font-bold text-cyan-500">Create Test</h1>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="name" className="block text-sm font-medium text-gray-700">Test Name</label>
            <input
              id="name"
              name="name"
              type="text"
              required
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 sm:text-md"
              value={testDetails.name}
              onChange={handleInputChange}
            />
          </div>
          <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
            <div>
              <label htmlFor="startTime" className="block text-sm font-medium text-gray-700">Start Time</label>
              <input
                id="startTime"
                name="startTime"
                type="datetime-local"
                required
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 sm:text-md"
                value={testDetails.startTime}
                onChange={handleInputChange}
              />
            </div>
            <div>
              <label htmlFor="endTime" className="block text-sm font-medium text-gray-700">End Time</label>
              <input
                id="endTime"
                name="endTime"
                type="datetime-local"
                required
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 sm:text-md"
                value={testDetails.endTime}
                onChange={handleInputChange}
              />
            </div>
          </div>
          <div>
            <label htmlFor="numberOfQuestions" className="block text-sm font-medium text-gray-700">Number of Questions</label>
            <input
              id="numberOfQuestions"
              name="numberOfQuestions"
              type="number"
              required
              min="0"
              max="200"
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 sm:text-md"
              value={testDetails.numberOfQuestions}
              onChange={handleInputChange}
            />
          </div>
          <div>
            <label htmlFor="numberOfChoices" className="block text-sm font-medium text-gray-700">Number of Choices</label>
            <input
              id="numberOfChoices"
              name="numberOfChoices"
              type="number"
              required
              min="2"
              max="7"
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm focus:ring-cyan-500 focus:border-cyan-500 sm:text-md"
              value={testDetails.numberOfChoices}
              onChange={handleInputChange}
            />
          </div>
          <div className="overflow-y-auto max-h-64" onScroll={handleScroll}>
            {generateAnswerInputs()}
          </div>
          <div>
            <button
              type="submit"
              className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-cyan-600 hover:bg-cyan-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500"
            >
              Create Test
            </button>
          </div>
        </form>
        {templateImage && (
          <div className="mt-6">
            <h2 className="text-xl font-bold mb-4">Test Template Image</h2>
            <img src={templateImage} alt="Test Template" />
          </div>
        )}
      </div>
    </div>
  );
};
