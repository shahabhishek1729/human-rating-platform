import { useState } from "react";
import { api } from "../../api";
import type { DelegationTask, SubtaskData } from "../../types";

interface SubtaskCardProps {
  subtask: SubtaskData;
  userInput: string;
  onInputChange: (id: number, value: string) => void;
  isExpanded: boolean;
  onToggleExpand: (id: number) => void;
}

function SubtaskCard({
  subtask,
  userInput,
  onInputChange,
  isExpanded,
  onToggleExpand,
}: SubtaskCardProps) {
  const needsInput = subtask.needs_human_input ?? false;
  const confidencePercent = Math.round(subtask.ai_confidence * 100);

  return (
    <div
      className={`border rounded-lg p-4 ${
        needsInput
          ? "border-orange-300 bg-orange-50"
          : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-4 mb-3">
        <h3 className="font-medium text-gray-900">{subtask.description}</h3>
        <span
          className={`px-2 py-1 rounded text-xs font-medium whitespace-nowrap ${
            needsInput
              ? "bg-orange-100 text-orange-800"
              : "bg-green-100 text-green-800"
          }`}
        >
          {needsInput ? "Input Needed" : `${confidencePercent}% Confident`}
        </span>
      </div>

      <div className="mb-4">
        <span className="text-sm text-gray-500">AI Answer: </span>
        <span className="text-gray-800 font-medium">{subtask.ai_answer}</span>
      </div>

      {needsInput ? (
        <div>
          <label className="block text-sm font-medium text-orange-800 mb-1">
            Your input required
          </label>
          <textarea
            value={userInput}
            onChange={(e) => onInputChange(subtask.id, e.target.value)}
            placeholder="Please verify or provide the correct answer..."
            className="w-full border border-orange-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent bg-white"
            rows={3}
          />
        </div>
      ) : (
        <div>
          {isExpanded ? (
            <div className="space-y-2">
              <textarea
                value={userInput}
                onChange={(e) => onInputChange(subtask.id, e.target.value)}
                placeholder="Enter your feedback..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                rows={2}
              />
              <button
                type="button"
                onClick={() => onToggleExpand(subtask.id)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => onToggleExpand(subtask.id)}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              Add feedback
            </button>
          )}
        </div>
      )}
    </div>
  );
}

interface DelegationInterfaceProps {
  task: DelegationTask;
  sessionToken: string;
  pid: string;
  experimentId: number;
  onComplete: () => void;
}

export function DelegationInterface({
  task,
  sessionToken,
  pid,
  experimentId,
  onComplete,
}: DelegationInterfaceProps) {
  const [userInputs, setUserInputs] = useState<Record<number, string>>({});
  const [expandedCards, setExpandedCards] = useState<Record<number, boolean>>(
    {},
  );
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleInputChange = (subtaskId: number, value: string) => {
    setUserInputs((prev) => ({ ...prev, [subtaskId]: value }));
  };

  const handleToggleExpand = (subtaskId: number) => {
    setExpandedCards((prev) => ({ ...prev, [subtaskId]: !prev[subtaskId] }));
  };

  const subtasksNeedingInput = task.delegation_data.filter(
    (s) => s.needs_human_input === true,
  );
  const allRequiredFilled = subtasksNeedingInput.every((s) =>
    userInputs[s.id]?.trim(),
  );

  const handleSubmit = async () => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const stringInputs: Record<string, string> = {};
      for (const [k, v] of Object.entries(userInputs)) {
        stringInputs[String(k)] = v;
      }
      await api.submitDelegation(
        sessionToken,
        pid,
        task.id,
        experimentId,
        stringInputs,
      );
      setSubmitted(true);
      onComplete();
    } catch {
      setSubmitError(
        "Sorry, an error occurred while submitting. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="p-6">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <h2 className="text-lg font-semibold text-green-900 mb-2">
            Submission Complete
          </h2>
          <p className="text-green-800">Redirecting you back to Prolific...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        <div className="mb-4">
          <h2 className="text-lg font-semibold text-gray-900">AI Analysis</h2>
          <p className="text-sm text-gray-600">
            Review the AI's work on each subtask. Low-confidence items require
            your input.
          </p>
        </div>

        {task.delegation_data.map((subtask) => (
          <SubtaskCard
            key={subtask.id}
            subtask={subtask}
            userInput={userInputs[subtask.id] || ""}
            onInputChange={handleInputChange}
            isExpanded={expandedCards[subtask.id] || false}
            onToggleExpand={handleToggleExpand}
          />
        ))}
      </div>

      <div className="border-t border-gray-200 p-4">
        {submitError && (
          <p className="text-sm text-red-600 text-center mb-2">{submitError}</p>
        )}
        <button
          onClick={handleSubmit}
          disabled={!allRequiredFilled || isSubmitting}
          className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? "Submitting..." : "Submit Answers"}
        </button>
        {!allRequiredFilled && subtasksNeedingInput.length > 0 && (
          <p className="text-sm text-orange-600 text-center mt-2">
            Please complete all required inputs before submitting.
          </p>
        )}
      </div>
    </div>
  );
}
