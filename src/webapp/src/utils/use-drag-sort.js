import { useCallback, useEffect, useRef, useState } from 'react';

// Distance to the top or bottom edge of the scroll area (px) where dragging scrolls it, and its speed (px per frame)
const SCROLL_EDGE = 48;
const SCROLL_SPEED = 12;
// The other rows make room smoothly
const MAKE_ROOM = 'transform 150ms ease';

// Where a dragged row lands: the number of the other rows whose middle is above the pointer
const dropIndex = (middles, y) => {
  const index = middles.findIndex((middle) => middle > y);
  return index === -1 ? middles.length : index;
};

const move = (list, from, to) => {
  const result = [...list];
  const [item] = result.splice(from, 1);
  result.splice(to, 0, item);
  return result;
};

/**
 * Sort a list by dragging its rows at a handle, with the mouse or a finger (pointer events).
 *
 * While dragging, the rows are only moved on the screen (CSS transform): the dragged row follows the pointer,
 * the others make room where it would land. The list changes when the row is dropped.
 * Near the edges of `scrollRef` the list scrolls.
 *
 * @returns {{ rowRef, handleProps, draggingKey }} `rowRef(key)` for each row element, `handleProps(key)`
 *   for its drag handle, the key of the dragged row (null if none)
 */
const useDragSort = ({ items, setItems, getKey, scrollRef }) => {
  const rows = useRef(new Map());
  const drag = useRef(null);
  // The latest values for the event handlers and the animation frames
  const latest = useRef();
  latest.current = { items, setItems, getKey, scrollRef };
  const [draggingKey, setDraggingKey] = useState(null);

  const rowRef = useCallback((key) => (element) => {
    if (element) rows.current.set(key, element);
    else rows.current.delete(key);
  }, []);

  const frame = useCallback(() => {
    const current = drag.current;
    if (!current) return;

    const area = latest.current.scrollRef?.current;
    if (area) {
      const { top, bottom } = area.getBoundingClientRect();
      if (current.y < top + SCROLL_EDGE) area.scrollTop -= SCROLL_SPEED;
      else if (current.y > bottom - SCROLL_EDGE) area.scrollTop += SCROLL_SPEED;
    }
    const scrolled = area ? area.scrollTop - current.scrollTop : 0;

    // The dragged row follows the pointer, also while the list scrolls
    const element = rows.current.get(current.key);
    if (element) element.style.transform = `translateY(${current.y - current.startY + scrolled}px)`;

    // Positions from the start of the drag: the rows on the screen are moved, not in the page
    current.index = dropIndex(current.middles.map((middle) => middle - scrolled), current.y);
    current.others.forEach((key, idx) => {
      const original = idx < current.from ? idx : idx + 1;
      const target = idx < current.index ? idx : idx + 1;
      const shift = (target - original) * current.height;
      if (current.shifts[key] !== shift) {
        current.shifts[key] = shift;
        const row = rows.current.get(key);
        if (row) row.style.transform = shift ? `translateY(${shift}px)` : '';
      }
    });
    current.frame = requestAnimationFrame(frame);
  }, []);

  const finish = useCallback((apply) => {
    const current = drag.current;
    if (!current) return;
    drag.current = null;
    cancelAnimationFrame(current.frame);
    [current.key, ...current.others].forEach((key) => {
      const row = rows.current.get(key);
      if (row) {
        row.style.transition = '';
        row.style.transform = '';
      }
    });
    setDraggingKey(null);

    const { items: list, setItems: update } = latest.current;
    if (apply && current.index !== current.from) update(move(list, current.from, current.index));
  }, []);

  useEffect(() => {
    const onMove = (event) => {
      if (drag.current?.pointerId === event.pointerId) drag.current.y = event.clientY;
    };
    const onUp = (event) => {
      if (drag.current?.pointerId === event.pointerId) finish(event.type === 'pointerup');
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onUp);
      if (drag.current) cancelAnimationFrame(drag.current.frame);
    };
  }, [finish]);

  const handleProps = (key) => ({
    onPointerDown: (event) => {
      if (drag.current || (event.pointerType === 'mouse' && event.button !== 0)) return;
      event.preventDefault();
      const { items: list, getKey: keyOf, scrollRef: scroller } = latest.current;
      const from = list.findIndex((item) => keyOf(item) === key);
      const others = list.map(keyOf).filter((other) => other !== key);
      const rectOf = (rowKey) => rows.current.get(rowKey)?.getBoundingClientRect() || { top: 0, height: 0 };
      others.forEach((other) => {
        const row = rows.current.get(other);
        if (row) row.style.transition = MAKE_ROOM;
      });
      drag.current = {
        key,
        pointerId: event.pointerId,
        startY: event.clientY,
        y: event.clientY,
        scrollTop: scroller?.current?.scrollTop || 0,
        from,
        index: from,
        others,
        middles: others.map((other) => rectOf(other).top + rectOf(other).height / 2),
        height: rectOf(key).height,
        shifts: {},
      };
      setDraggingKey(key);
      drag.current.frame = requestAnimationFrame(frame);
    },
    // A finger on the handle drags the row instead of scrolling the page
    style: { touchAction: 'none', cursor: draggingKey === key ? 'grabbing' : 'grab' },
  });

  return { rowRef, handleProps, draggingKey };
};

export { dropIndex };
export default useDragSort;
