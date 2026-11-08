import { Buffer } from 'buffer';
import { TextDecoder } from 'util';

import { socketRequest } from './index';

// Fake sockets: records the Dealers and what they sent, answers are delivered by the test
jest.mock('jszmq', () => {
  const { Buffer: FakeBuffer } = jest.requireActual('buffer');

  class FakeSocket {
    constructor() {
      this.handlers = {};
      this.sent = [];
      this.connect = jest.fn();
      this.subscribe = jest.fn();
      FakeSocket.created.push(this);
    }

    on(event, handler) {
      this.handlers[event] = handler;
    }

    send(msg) {
      this.sent.push(msg);
    }
  }
  FakeSocket.created = [];

  class Dealer extends FakeSocket {}
  class Sub extends FakeSocket {}

  return { Buffer: FakeBuffer, Dealer, Sub, FakeSocket };
});

const { Dealer, FakeSocket } = jest.requireMock('jszmq');

// jsdom has no TextDecoder, decodeMessage needs one
if (!global.TextDecoder) global.TextDecoder = TextDecoder;

const dealers = () => FakeSocket.created.filter(socket => socket instanceof Dealer);

const sentPayload = (index) => JSON.parse(dealers()[0].sent[index][1]);

// Answer as the core sends it: empty delimiter frame, then the JSON reply
const answer = (reply) => dealers()[0].handlers.message(
  Buffer.alloc(0),
  Buffer.from(JSON.stringify(reply)),
);

afterEach(() => jest.useRealTimers());

test('parallel requests share one connection and get their own answers', async () => {
  const first = socketRequest('player', 'ctrl', 'get_folder_coverart', { folder: 'A' });
  const second = socketRequest('cards', 'list_cards', null, {});

  expect(dealers()).toHaveLength(1);
  expect(dealers()[0].connect).toHaveBeenCalledTimes(1);

  const [delimiter] = dealers()[0].sent[0];
  expect(delimiter).toHaveLength(0);
  expect(sentPayload(0)).toMatchObject({
    package: 'player', plugin: 'ctrl', method: 'get_folder_coverart', kwargs: { folder: 'A' },
  });

  // Answers in the reverse order
  answer({ id: sentPayload(1).id, result: { card: {} } });
  answer({ id: sentPayload(0).id, result: 'a.jpg' });

  await expect(first).resolves.toBe('a.jpg');
  await expect(second).resolves.toEqual({ card: {} });

  const third = socketRequest('player', 'ctrl', 'play', {});
  expect(dealers()).toHaveLength(1);
  answer({ id: sentPayload(2).id, result: null });
  await expect(third).resolves.toBeNull();
});

test('an error answer rejects the request', async () => {
  const promise = socketRequest('player', 'ctrl', 'nope', {});
  const index = dealers()[0].sent.length - 1;

  answer({ id: sentPayload(index).id, error: { message: 'unknown method' } });

  await expect(promise).rejects.toBe('unknown method');
});

test('a request without answer fails after the timeout, a late answer is ignored', async () => {
  jest.useFakeTimers();
  const promise = socketRequest('player', 'ctrl', 'slow', {});
  const index = dealers()[0].sent.length - 1;

  jest.advanceTimersByTime(60000);
  await expect(promise).rejects.toMatch(/No answer/);

  expect(() => answer({ id: sentPayload(index).id, result: 'late' })).not.toThrow();
});
