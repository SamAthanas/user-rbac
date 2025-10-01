import { notification } from 'antd';

export const showSuccessToast = (message) => {
  notification.success({
    message: 'Success',
    description: message,
    placement: 'bottomRight',
    duration: 3,
  });
};

export const showErrorToast = (message) => {
  notification.error({
    message: 'Error',
    description: message,
    placement: 'bottomRight',
    duration: 5,
  });
};

export const showInfoToast = (message) => {
  notification.info({
    message: 'Info',
    description: message,
    placement: 'bottomRight',
    duration: 3,
  });
};

export const showWarningToast = (message) => {
  notification.warning({
    message: 'Warning',
    description: message,
    placement: 'bottomRight',
    duration: 4,
  });
};
