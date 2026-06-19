/**
 * Sentry Error Tracking Configuration
 * 
 * Initializes Sentry SDK for frontend error tracking and performance monitoring.
 * Includes release tracking via Git commit SHA.
 */

import * as Sentry from '@sentry/react';

/**
 * Get Git commit SHA for release tracking
 * This is typically injected during build via environment variables
 */
const getRelease = (): string | undefined => {
  // Try to get from build-time environment variable
  const gitCommit = import.meta.env.VITE_GIT_COMMIT_SHA;
  
  if (gitCommit) {
    return gitCommit;
  }
  
  // Fallback to app version
  return import.meta.env.VITE_APP_VERSION || '1.0.0';
};

/**
 * Initialize Sentry SDK with configuration
 */
export const initSentry = (): void => {
  const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
  
  // Only initialize if DSN is configured
  if (!sentryDsn) {
    console.info('Sentry DSN not configured - error tracking disabled');
    return;
  }
  
  const environment = import.meta.env.VITE_SENTRY_ENVIRONMENT || import.meta.env.MODE || 'development';
  const release = getRelease();
  
  Sentry.init({
    dsn: sentryDsn,
    environment,
    release,
    
    // Performance Monitoring
    integrations: [
      // Automatic instrumentation for React components
      new Sentry.BrowserTracing({
        // Set sampling rate for performance monitoring
        tracePropagationTargets: [
          'localhost',
          /^\//,
          /^https:\/\/[^/]*\.yourdomain\.com/,
        ],
      }),
      // Replay integration for session recording (optional)
      new Sentry.Replay({
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],
    
    // Performance monitoring sample rate (10% of transactions)
    tracesSampleRate: parseFloat(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE || '0.1'),
    
    // Session replay sample rate
    replaysSessionSampleRate: 0.1, // 10% of sessions
    replaysOnErrorSampleRate: 1.0, // 100% of sessions with errors
    
    // Capture 100% of errors
    sampleRate: 1.0,
    
    // Attach stack traces to messages
    attachStacktrace: true,
    
    // Enable automatic breadcrumbs
    beforeBreadcrumb(breadcrumb) {
      // Filter out sensitive breadcrumbs if needed
      if (breadcrumb.category === 'console' && breadcrumb.level === 'debug') {
        return null;
      }
      return breadcrumb;
    },
    
    // Filter out sensitive data before sending to Sentry
    beforeSend(event, hint) {
      // Remove sensitive data from event context
      if (event.request?.headers) {
        delete event.request.headers['Authorization'];
        delete event.request.headers['Cookie'];
      }
      
      // Log errors locally in development
      if (environment === 'development') {
        console.error('Sentry Event:', event, hint);
      }
      
      return event;
    },
    
    // Ignore specific errors
    ignoreErrors: [
      // Browser extensions
      'top.GLOBALS',
      // Random plugins/extensions
      'originalCreateNotification',
      'canvas.contentDocument',
      'MyApp_RemoveAllHighlights',
      // Network errors that are expected
      'NetworkError',
      'Network request failed',
      // Unhandled promise rejections from third-party code
      'Non-Error promise rejection captured',
    ],
    
    // Deny URLs from being sent to Sentry
    denyUrls: [
      // Browser extensions
      /extensions\//i,
      /^chrome:\/\//i,
      /^moz-extension:\/\//i,
    ],
  });
  
  console.info(`Sentry initialized for environment: ${environment}, release: ${release}`);
};

/**
 * Set user context for Sentry error tracking
 * 
 * @param userId - User ID or session ID
 * @param email - User email (optional)
 * @param username - Username (optional)
 */
export const setSentryUser = (
  userId: string,
  email?: string,
  username?: string,
): void => {
  Sentry.setUser({
    id: userId,
    email,
    username,
  });
};

/**
 * Clear user context from Sentry
 */
export const clearSentryUser = (): void => {
  Sentry.setUser(null);
};

/**
 * Manually capture an exception
 * 
 * @param error - Error to capture
 * @param context - Additional context
 */
export const captureException = (
  error: Error,
  context?: Record<string, unknown>,
): void => {
  if (context) {
    Sentry.setContext('custom', context);
  }
  Sentry.captureException(error);
};
