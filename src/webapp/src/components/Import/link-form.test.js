import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';

import request from '../../utils/request';
import LinkForm from './link-form';

// With a factory: an automatic mock would load the real module, which connects the sockets
jest.mock('../../utils/request', () => ({ __esModule: true, default: jest.fn() }));

jest.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (key) => key }),
}));

afterEach(() => jest.clearAllMocks());

const submit = () => {
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'https://youtu.be/v' } });
  fireEvent.click(screen.getByRole('button', { name: 'import.link.load' }));
};

test('shows the loading right after the click, before the core publishes a status', async () => {
  // The core does not answer yet
  request.mockImplementation(() => new Promise(() => {}));
  render(<LinkForm status={{ state: 'idle' }} disabled={false} />);
  submit();

  expect(await screen.findByText('import.link.loading')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'import.link.load' })).toBeDisabled();
  expect(request).toHaveBeenCalledWith('ytimportFetchInfo', { url: 'https://youtu.be/v' });
  // Cancelling only once the core is fetching
  expect(screen.queryByText('import.cancel')).not.toBeInTheDocument();
});

test('the published status takes over, an error ends the loading', async () => {
  request.mockResolvedValue({ result: null });
  const { rerender } = render(<LinkForm status={{ state: 'idle' }} disabled={false} />);
  submit();
  rerender(<LinkForm status={{ state: 'fetching', url: 'https://youtu.be/v' }} disabled />);
  expect(await screen.findByText('import.cancel')).toBeInTheDocument();

  request.mockResolvedValue({ error: 'Please enter a link' });
  rerender(<LinkForm status={{ state: 'error' }} disabled={false} />);
  submit();
  expect(await screen.findByText('Please enter a link')).toBeInTheDocument();
  expect(screen.queryByText('import.link.loading')).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'import.link.load' })).toBeEnabled();
});
