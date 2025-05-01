import { useState } from 'react';
// Consider adding an icon library like react-icons if desired
// import { FiCopy } from 'react-icons/fi';

const AddPythonTool = () => {
  const [functionCode, setFunctionCode] = useState(`def get_weather(location, unit="celsius"):
    """Get the current weather in a given location.

    Args:
        location (str): The city and state, e.g., "San Francisco, CA"
        unit (str): The unit of temperature, either "celsius" or "fahrenheit".
            Defaults to "celsius".

    Returns:
        dict: A dictionary containing the weather information.
    """
    import json
    # This is a mock implementation
    weather_data = {
        "location": location,
        "temperature": 22,
        "unit": unit,
        "condition": "Sunny"
    }
    return weather_data`);
  const [functionName, setFunctionName] = useState('getWeather');
  const [saveAsTemplate, setSaveAsTemplate] = useState(false); // Added state for checkbox
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleCopyCode = () => {
    navigator.clipboard.writeText(functionCode)
      .then(() => {
        // Optional: Show a temporary success message/tooltip
        console.log('Code copied to clipboard!');
      })
      .catch(err => {
        console.error('Failed to copy code: ', err);
        // Optional: Show an error message
      });
  };

  const handleSubmit = () => {
    setIsSubmitting(true);
    setError(''); // Clear previous errors
    // Simulate API call
    setTimeout(() => {
      setIsSubmitting(false);
      // Example: Toggle error for demonstration
      // setError(prev => prev ? '' : 'Function name already exists. Please choose another.');
      console.log('Submitting:', { functionName, functionCode, saveAsTemplate });
      // On successful submission, you might want to redirect or show a success message
    }, 1500);
  };

  return (
    // Main container using full height and width with padding and a subtle background
    <div className="min-h-screen w-full bg-gradient-to-br from-blue-50 to-indigo-100 p-4 sm:p-8 flex items-center justify-center">
      {/* Card container - takes full width up to a reasonable max, centered */}
      <div className="bg-white rounded-xl shadow-xl p-6 sm:p-8 md:p-10 w-full max-w-6xl"> {/* Increased max-width */}
        <h2 className="text-3xl font-bold text-gray-800 mb-4 pb-3 border-b border-gray-200">
          Add Python Function Tool
        </h2>

        {/* Error Message Area */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-500 text-red-800 p-4 mb-6 rounded-md shadow-sm" role="alert">
            <p className="font-semibold">Error</p>
            <p>{error}</p>
          </div>
        )}

        {/* Form Area */}
        <div className="space-y-6 md:space-y-8">
          {/* Responsive Grid Layout */}
          <div className="lg:grid lg:grid-cols-2 lg:gap-x-8 lg:gap-y-6">

            {/* Function Name Section */}
            <div className="space-y-2 mb-6 lg:mb-0">
              <label htmlFor="functionName" className="block text-base font-semibold text-gray-700 tracking-wide">
                Function Name
              </label>
              <input
                id="functionName"
                type="text"
                value={functionName}
                onChange={(e) => setFunctionName(e.target.value)}
                placeholder="e.g., get_current_weather"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition duration-150 ease-in-out text-gray-900"
              />
              <p className="text-sm text-gray-500">A unique name for your Python function.</p>
            </div>

            {/* Placeholder for potential second column element or spacing */}
            {/* <div className="hidden lg:block"></div> */}

            {/* Python Code Section (Spans full width in the grid layout for visual balance, or adjust col-span) */}
            <div className="space-y-2 lg:col-span-2">
              <div className="flex justify-between items-center">
                <label htmlFor="functionCode" className="block text-base font-semibold text-gray-700 tracking-wide">
                  Python Code
                </label>
                <span className="text-sm font-medium text-indigo-600">Python 3.x Compatible</span>
              </div>
              <div className="relative group">
                <textarea
                  id="functionCode"
                  value={functionCode}
                  onChange={(e) => setFunctionCode(e.target.value)}
                  rows={18} // Increased rows for better vertical space
                  placeholder="Paste your Python function code here..."
                  className="w-full px-4 py-3 font-mono text-sm border border-gray-300 rounded-lg shadow-sm focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-gray-50/50 resize-y transition duration-150 ease-in-out" // Added resize-y
                  style={{ lineHeight: '1.6' }} // Slightly increased line height for readability
                />
                <button
                  onClick={handleCopyCode}
                  title="Copy code"
                  className="absolute top-3 right-3 text-gray-500 hover:text-indigo-600 bg-white/70 hover:bg-gray-100 p-1.5 rounded-md transition duration-150 ease-in-out opacity-0 group-hover:opacity-100 focus:opacity-100"
                >
                  {/* Example using SVG for copy icon (replace with react-icons if preferred) */}
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  {/* <FiCopy className="h-5 w-5" /> */}
                </button>
              </div>
              <p className="text-sm text-gray-500 italic">
                Ensure your function includes proper docstrings for description, arguments, and return values.
              </p>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="flex flex-col sm:flex-row justify-between items-center pt-6 border-t border-gray-200 mt-8">
            <div className="flex items-center space-x-3 mb-4 sm:mb-0">
              <input
                type="checkbox"
                id="saveTemplate"
                checked={saveAsTemplate}
                onChange={(e) => setSaveAsTemplate(e.target.checked)}
                className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              />
              <label htmlFor="saveTemplate" className="text-sm font-medium text-gray-700 cursor-pointer">
                Save as template for future use
              </label>
            </div>

            <button
              onClick={handleSubmit}
              disabled={isSubmitting || !functionName || !functionCode} // Basic validation disabling
              className={`inline-flex items-center justify-center px-8 py-3 text-base font-semibold text-white rounded-lg shadow-md transition duration-150 ease-in-out ${
                (isSubmitting || !functionName || !functionCode)
                  ? 'bg-indigo-300 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500'
              }`}
            >
              {isSubmitting ? (
                <>
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Adding Tool...
                </>
              ) : (
                'Add Python Tool'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AddPythonTool;