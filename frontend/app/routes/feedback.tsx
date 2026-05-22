/* eslint-disable react-refresh/only-export-components */
import {
  useActionData,
  useNavigation,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
  type MetaFunction,
} from 'react-router';
import {
  FeedbackPage,
  type FeedbackActionData,
} from '../../src/pages/FeedbackPage';
import { buildSeoMeta } from '../../src/config/seo';
import { serverFetch } from '../lib/server-api';

const topicOptions = new Set([
  'Correction',
  'Question',
  'Comments or Suggestions',
  'Harmful language',
  'Other',
]);

function formString(formData: FormData, name: string) {
  const value = formData.get(name);
  return typeof value === 'string' ? value.trim() : '';
}

function getErrorMessage(payload: unknown) {
  if (!payload || typeof payload !== 'object') {
    return 'We could not send your feedback. Please try again in a moment.';
  }

  if ('message' in payload && typeof payload.message === 'string') {
    return payload.message;
  }

  if ('detail' in payload && typeof payload.detail === 'string') {
    return payload.detail;
  }

  return 'We could not send your feedback. Please try again in a moment.';
}

export function loader({ request }: LoaderFunctionArgs) {
  return { currentUrl: new URL(request.url).href };
}

export async function action({
  request,
}: ActionFunctionArgs): Promise<FeedbackActionData> {
  const formData = await request.formData();
  const values = {
    name: formString(formData, 'name'),
    email_address: formString(formData, 'email_address'),
    topic: formString(formData, 'topic'),
    description: formString(formData, 'description'),
  };
  const contactInfo = formString(formData, 'contact_info');
  const fieldErrors: NonNullable<
    Extract<FeedbackActionData, { status: 'error' }>['fieldErrors']
  > = {};

  if (!values.topic || !topicOptions.has(values.topic)) {
    fieldErrors.topic = 'Select a feedback topic.';
  }

  if (!values.description) {
    fieldErrors.description = 'Enter your feedback.';
  }

  if (
    values.email_address &&
    !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email_address)
  ) {
    fieldErrors.email_address = 'Enter a valid email address.';
  }

  if (Object.keys(fieldErrors).length > 0) {
    return {
      status: 'error',
      message: 'Please review the highlighted fields.',
      fieldErrors,
      values,
    };
  }

  try {
    const response = await serverFetch('/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...values,
        contact_info: contactInfo,
        source_url: request.headers.get('referer') || new URL(request.url).href,
        user_agent: request.headers.get('user-agent') || '',
      }),
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      return {
        status: 'error',
        message: getErrorMessage(payload),
        values,
      };
    }

    return {
      status: 'success',
      message: 'Thank you for your feedback. Your message has been sent.',
    };
  } catch (error) {
    console.error('Feedback submission failed:', error);
    return {
      status: 'error',
      message: 'We could not send your feedback. Please try again in a moment.',
      values,
    };
  }
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: 'Feedback',
    description:
      'Send feedback to the Big Ten Academic Alliance Geoportal team.',
    url: data?.currentUrl,
  });

export default function Feedback() {
  const actionData = useActionData<typeof action>();
  const navigation = useNavigation();

  return (
    <FeedbackPage
      actionData={actionData}
      isSubmitting={navigation.state === 'submitting'}
    />
  );
}
