import { Send } from 'lucide-react';
import { Form } from 'react-router';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { Seo } from '../components/Seo';

export type FeedbackFormValues = {
  name: string;
  email_address: string;
  topic: string;
  description: string;
};

export type FeedbackFieldErrors = Partial<
  Record<keyof FeedbackFormValues, string>
>;

export type FeedbackActionData =
  | {
      status: 'success';
      message: string;
    }
  | {
      status: 'error';
      message: string;
      fieldErrors?: FeedbackFieldErrors;
      values?: FeedbackFormValues;
    };

const topicOptions = [
  'Correction',
  'Question',
  'Comments or Suggestions',
  'Harmful language',
  'Other',
];

const inputClass =
  'mt-2 block w-full border border-gray-300 bg-white px-3 py-2 text-base text-gray-900 shadow-sm focus:border-brand-active focus:outline-none focus:ring-2 focus:ring-brand-active/30';
const labelClass = 'block text-sm font-semibold text-gray-900';

function fieldError(
  actionData: FeedbackActionData | undefined,
  fieldName: keyof FeedbackFormValues
) {
  return actionData?.status === 'error'
    ? actionData.fieldErrors?.[fieldName]
    : undefined;
}

function fieldValue(
  actionData: FeedbackActionData | undefined,
  fieldName: keyof FeedbackFormValues
) {
  return actionData?.status === 'error'
    ? actionData.values?.[fieldName] || ''
    : '';
}

export function FeedbackPage({
  actionData,
  isSubmitting = false,
}: {
  actionData?: FeedbackActionData;
  isSubmitting?: boolean;
}) {
  const success = actionData?.status === 'success';
  const formKey = success ? 'feedback-sent' : 'feedback-editing';

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Seo
        title="Feedback"
        description="Send feedback to the Big Ten Academic Alliance Geoportal team."
      />
      <Header />
      <main className="flex-1">
        <section className="bg-white border-b border-gray-200">
          <div className="max-w-5xl px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
            <p className="text-sm font-semibold uppercase text-brand">
              Contact Us
            </p>
            <h1 className="mt-3 text-4xl font-semibold text-gray-950 sm:text-5xl">
              Feedback
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-gray-700">
              We value your thoughts and opinions. We will reply to all comments
              shortly.
            </p>
          </div>
        </section>

        <section className="bg-gray-50">
          <div className="max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
            {actionData && (
              <div
                role={success ? 'status' : 'alert'}
                className={`mb-6 border px-4 py-3 text-sm leading-6 ${
                  success
                    ? 'border-green-200 bg-green-50 text-green-900'
                    : 'border-red-200 bg-red-50 text-red-900'
                }`}
              >
                {actionData.message}
              </div>
            )}

            <Form key={formKey} method="post" className="max-w-3xl space-y-8">
              <fieldset className="space-y-5">
                <legend className="text-xl font-semibold text-gray-950">
                  About You
                </legend>
                <div>
                  <label htmlFor="feedback-name" className={labelClass}>
                    Name (optional)
                  </label>
                  <input
                    id="feedback-name"
                    name="name"
                    type="text"
                    autoComplete="name"
                    maxLength={120}
                    defaultValue={fieldValue(actionData, 'name')}
                    className={inputClass}
                  />
                  {fieldError(actionData, 'name') && (
                    <p className="mt-2 text-sm text-red-700">
                      {fieldError(actionData, 'name')}
                    </p>
                  )}
                </div>

                <div>
                  <label htmlFor="feedback-email" className={labelClass}>
                    Email Address (optional)
                  </label>
                  <input
                    id="feedback-email"
                    name="email_address"
                    type="email"
                    autoComplete="email"
                    maxLength={254}
                    defaultValue={fieldValue(actionData, 'email_address')}
                    className={inputClass}
                  />
                  {fieldError(actionData, 'email_address') && (
                    <p className="mt-2 text-sm text-red-700">
                      {fieldError(actionData, 'email_address')}
                    </p>
                  )}
                </div>
              </fieldset>

              <fieldset className="space-y-5">
                <legend className="text-xl font-semibold text-gray-950">
                  Leave Your Feedback
                </legend>
                <div>
                  <label htmlFor="feedback-topic" className={labelClass}>
                    Topic
                  </label>
                  <select
                    id="feedback-topic"
                    name="topic"
                    required
                    defaultValue={fieldValue(actionData, 'topic')}
                    className={inputClass}
                  >
                    <option value="">Please select</option>
                    {topicOptions.map((topic) => (
                      <option key={topic} value={topic}>
                        {topic}
                      </option>
                    ))}
                  </select>
                  {fieldError(actionData, 'topic') && (
                    <p className="mt-2 text-sm text-red-700">
                      {fieldError(actionData, 'topic')}
                    </p>
                  )}
                </div>

                <div>
                  <label htmlFor="feedback-description" className={labelClass}>
                    Description
                  </label>
                  <textarea
                    id="feedback-description"
                    name="description"
                    required
                    rows={8}
                    maxLength={5000}
                    defaultValue={fieldValue(actionData, 'description')}
                    className={inputClass}
                  />
                  {fieldError(actionData, 'description') && (
                    <p className="mt-2 text-sm text-red-700">
                      {fieldError(actionData, 'description')}
                    </p>
                  )}
                </div>

                <div
                  className="absolute -left-[10000px] top-auto h-px w-px overflow-hidden"
                  aria-hidden="true"
                >
                  <label htmlFor="feedback-contact-info">Contact info</label>
                  <input
                    id="feedback-contact-info"
                    name="contact_info"
                    type="text"
                    tabIndex={-1}
                    autoComplete="off"
                  />
                </div>
              </fieldset>

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex min-h-11 items-center justify-center gap-2 bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-[#002f47] focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-active focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-65"
              >
                <Send className="h-4 w-4" aria-hidden />
                {isSubmitting ? 'Sending...' : 'Send Feedback'}
              </button>
            </Form>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
