import { v4 as uuidv4 } from 'uuid';
import * as zmq from 'jszmq';

import {
  PUBSUB_ENDPOINT,
  REQRES_ENDPOINT,
  SUBSCRIPTIONS,
} from '../config';
import {
  decodeMessage,
  decodePubSubMessage,
  encodeMessage,
  preparePayload
} from './utils';

const socket_sub = new zmq.Sub();

SUBSCRIPTIONS.forEach(
  (topic) => socket_sub.subscribe(topic)
);

socket_sub.connect(PUBSUB_ENDPOINT);

const socketEvents = ({ setState, events = [] }) => {
  socket_sub.on('message', (_topic, _payload) => {
    const { topic, data, error } = decodePubSubMessage(_topic, _payload);

    if (events.includes(topic) && data) {
      setState(state => ({ ...state, [topic]: data }));
      if (topic !== 'playerstatus') {
        console.log(topic, data, events);
      }
    }

    if (error) {
      // TODO: Better error handling
      console.error(`[PubSub][${topic}]: ${error}`);
    }
  });
};

const initSockets = ({ setState, events }) => {
  socketEvents({ setState, events });
};

// Requests without answer fail after this time, e.g. if the core restarted meanwhile
const REQUEST_TIMEOUT_MS = 60000;

// Requests waiting for their answer: id -> { resolve, reject, timer }
const pendingRequests = new Map();

// All requests share one connection (a new one per request would pile up open WebSockets in the
// browser and slow down pages with many requests). A Dealer, unlike Req, may send further requests
// before the answer came; the core's REP socket answers them one after the other. jszmq reconnects
// by itself and keeps requests until connected.
let socket_req;

const handleAnswer = (delimiter, msg) => {
  const { id, error, result } = decodeMessage(msg);
  const pending = pendingRequests.get(id);
  // Unknown ID: e.g. the answer came after the timeout
  if (!pending) return;

  pendingRequests.delete(id);
  clearTimeout(pending.timer);

  if (error && error.message) {
    pending.reject(error.message);
  }
  else {
    pending.resolve(result);
  }
};

const getRequestSocket = () => {
  if (!socket_req) {
    socket_req = new zmq.Dealer();
    socket_req.on('message', handleAnswer);

    try {
      socket_req.connect(REQRES_ENDPOINT);
    }
    catch (error) {
      console.error(`WebSocket connection to '${REQRES_ENDPOINT} failed: `, error);
    }
  }
  return socket_req;
};

const socketRequest = (_package, plugin, method, kwargs) => (
  new Promise((resolve, reject) => {
    const requestId = uuidv4();

    const timer = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(`No answer within ${REQUEST_TIMEOUT_MS / 1000} s`);
    }, REQUEST_TIMEOUT_MS);
    pendingRequests.set(requestId, { resolve, reject, timer });

    const payload = preparePayload(
      requestId,
      _package,
      plugin,
      method,
      kwargs,
    );
    // The empty frame stands in for the envelope that a Req socket would add
    getRequestSocket().send([zmq.Buffer.alloc(0), encodeMessage(payload)]);
  })
);

export {
  initSockets,
  socketRequest,
};
