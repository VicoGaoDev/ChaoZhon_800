import { computed, nextTick, onBeforeUnmount, ref, type Ref } from "vue";

type SortableItem = { id: string };

const DEFAULT_THRESHOLD = 6;
const SWAP_MS = 240;
const SWAP_EASING = "cubic-bezier(0.22, 1, 0.36, 1)";
const DRAG_SCALE = 1.04;

export function usePointerSortableList<T extends SortableItem>(
  items: Ref<T[]>,
  options?: {
    threshold?: number;
    ignoreSelector?: string;
    container?: Ref<HTMLElement | null>;
  },
) {
  const threshold = options?.threshold ?? DEFAULT_THRESHOLD;
  const ignoreSelector = options?.ignoreSelector ?? "button, a, input, textarea, [data-no-sort]";
  const draggingId = ref<string | null>(null);
  const dragOverId = ref<string | null>(null);
  const isSorting = computed(() => Boolean(draggingId.value));

  let pointerId: number | null = null;
  let startIndex = -1;
  let startX = 0;
  let startY = 0;
  let active = false;
  let suppressClick = false;
  let slotsReady = true;
  let settleToken = 0;
  let flipToken = 0;
  let lastX = 0;
  let lastY = 0;
  let grabOffsetX = 0;
  let grabOffsetY = 0;
  let layoutLeft = 0;
  let layoutTop = 0;
  let layoutWidth = 0;
  let layoutHeight = 0;
  let slotRects = new Map<string, DOMRect>();

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function itemElements() {
    const root = options?.container?.value ?? document;
    return Array.from(root.querySelectorAll<HTMLElement>("[data-sortable-id]"));
  }

  function findElement(id: string | null) {
    if (!id) return null;
    const root = options?.container?.value ?? document;
    return root.querySelector<HTMLElement>(`[data-sortable-id="${CSS.escape(id)}"]`);
  }

  function findIndexById(id: string | null) {
    if (!id) return -1;
    return items.value.findIndex((item) => item.id === id);
  }

  function moveItem(fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;
    if (fromIndex >= items.value.length || toIndex >= items.value.length) return;
    const next = [...items.value];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    items.value = next;
  }

  function shouldIgnore(target: EventTarget | null) {
    return target instanceof Element && Boolean(target.closest(ignoreSelector));
  }

  function dragTransform(clientX: number, clientY: number) {
    const scaleFixX = ((1 - DRAG_SCALE) * layoutWidth) / 2;
    const scaleFixY = ((1 - DRAG_SCALE) * layoutHeight) / 2;
    const x = clientX - grabOffsetX - layoutLeft - scaleFixX;
    const y = clientY - grabOffsetY - layoutTop - scaleFixY;
    return `translate3d(${x}px, ${y}px, 0) scale(${DRAG_SCALE})`;
  }

  function clearMotion(element: HTMLElement) {
    element.getAnimations().forEach((animation) => animation.cancel());
    element.style.transition = "";
    element.style.transform = "";
    element.style.zIndex = "";
    element.style.pointerEvents = "";
  }

  function rememberSlots(layouts: Map<string, DOMRect>) {
    slotRects = layouts;
    const draggingRect = draggingId.value ? layouts.get(draggingId.value) : undefined;
    if (!draggingRect) return;
    layoutLeft = draggingRect.left;
    layoutTop = draggingRect.top;
    layoutWidth = draggingRect.width;
    layoutHeight = draggingRect.height;
  }

  function applyDragPosition(clientX: number, clientY: number) {
    const element = findElement(draggingId.value);
    if (!element) return;
    element.getAnimations().forEach((animation) => animation.cancel());
    element.style.transition = "none";
    element.style.zIndex = "5";
    element.style.pointerEvents = "none";
    element.style.transform = dragTransform(clientX, clientY);
  }

  function captureVisualRects() {
    const rects = new Map<string, DOMRect>();
    itemElements().forEach((element) => {
      const id = element.dataset.sortableId || "";
      if (id) rects.set(id, element.getBoundingClientRect());
    });
    return rects;
  }

  function measureLayouts() {
    const elements = itemElements();
    const previous = elements.map((element) => ({
      transform: element.style.transform,
      transition: element.style.transition,
    }));
    elements.forEach((element) => {
      element.getAnimations().forEach((animation) => animation.cancel());
      element.style.transition = "none";
      element.style.transform = "none";
    });
    const layouts = new Map<string, DOMRect>();
    elements.forEach((element, index) => {
      const id = element.dataset.sortableId || "";
      if (id) layouts.set(id, element.getBoundingClientRect());
      element.style.transform = previous[index].transform;
      element.style.transition = previous[index].transition;
    });
    return layouts;
  }

  function animateShift(element: HTMLElement, dx: number, dy: number, token: number) {
    if (prefersReducedMotion() || (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5)) {
      element.style.transform = "";
      return;
    }
    element.style.transition = "none";
    element.style.transform = "";
    element.getAnimations().forEach((animation) => animation.cancel());
    const animation = element.animate(
      [
        { transform: `translate3d(${dx}px, ${dy}px, 0)` },
        { transform: "translate3d(0, 0, 0)" },
      ],
      { duration: SWAP_MS, easing: SWAP_EASING, fill: "both" },
    );
    animation.onfinish = () => {
      if (token !== flipToken) return;
      animation.cancel();
      element.style.transition = "";
      element.style.transform = "";
    };
  }

  function settleDraggedItem() {
    const id = draggingId.value;
    const element = findElement(id);
    const token = ++settleToken;
    if (!element || !id) {
      draggingId.value = null;
      dragOverId.value = null;
      return;
    }
    const from = element.style.transform;
    element.getAnimations().forEach((animation) => animation.cancel());
    element.style.transition = "none";
    element.style.transform = "";
    element.style.pointerEvents = "none";
    if (!from || prefersReducedMotion()) {
      clearMotion(element);
      if (token === settleToken && !active) {
        draggingId.value = null;
        dragOverId.value = null;
      }
      return;
    }
    const animation = element.animate(
      [{ transform: from }, { transform: "translate3d(0, 0, 0) scale(1)" }],
      { duration: SWAP_MS, easing: SWAP_EASING, fill: "both" },
    );
    animation.onfinish = () => {
      if (token !== settleToken || active) return;
      animation.cancel();
      clearMotion(element);
      if (draggingId.value === id) {
        draggingId.value = null;
        dragOverId.value = null;
      }
    };
  }

  function playFlip(before: Map<string, DOMRect>) {
    const token = ++flipToken;
    nextTick(() => {
      if (token !== flipToken) return;
      const layouts = measureLayouts();
      rememberSlots(layouts);
      layouts.forEach((rect, id) => {
        const element = findElement(id);
        const first = before.get(id);
        if (!element || !first) return;
        if (id === draggingId.value) return;
        animateShift(element, first.left - rect.left, first.top - rect.top, token);
      });
      slotsReady = true;
      if (active) {
        applyDragPosition(lastX, lastY);
        return;
      }
      const draggingElement = findElement(draggingId.value);
      const first = draggingId.value ? before.get(draggingId.value) : undefined;
      const last = draggingId.value ? layouts.get(draggingId.value) : undefined;
      if (draggingElement && first && last) {
        const scaleFixX = ((1 - DRAG_SCALE) * last.width) / 2;
        const scaleFixY = ((1 - DRAG_SCALE) * last.height) / 2;
        draggingElement.style.transform = `translate3d(${first.left - last.left - scaleFixX}px, ${first.top - last.top - scaleFixY}px, 0) scale(${DRAG_SCALE})`;
      }
      settleDraggedItem();
    });
  }

  function findSlotAt(clientX: number, clientY: number) {
    const home = draggingId.value ? slotRects.get(draggingId.value) : undefined;
    if (!home) return null;
    let bestId: string | null = null;
    let bestDistance = Math.hypot(clientX - (home.left + home.width / 2), clientY - (home.top + home.height / 2));
    slotRects.forEach((rect, id) => {
      if (id === draggingId.value) return;
      const distance = Math.hypot(clientX - (rect.left + rect.width / 2), clientY - (rect.top + rect.height / 2));
      if (distance < bestDistance) {
        bestDistance = distance;
        bestId = id;
      }
    });
    return bestId;
  }

  function beginDrag(clientX: number, clientY: number) {
    const id = items.value[startIndex]?.id ?? null;
    const element = findElement(id);
    if (!id || !element) return;
    settleToken += 1;
    active = true;
    suppressClick = true;
    draggingId.value = id;
    const rect = element.getBoundingClientRect();
    grabOffsetX = clientX - rect.left;
    grabOffsetY = clientY - rect.top;
    layoutLeft = rect.left;
    layoutTop = rect.top;
    layoutWidth = rect.width;
    layoutHeight = rect.height;
    rememberSlots(measureLayouts());
    applyDragPosition(clientX, clientY);
  }

  function teardown() {
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("pointerup", handlePointerUp);
    window.removeEventListener("pointercancel", handlePointerUp);
  }

  function handlePointerMove(event: PointerEvent) {
    if (event.pointerId !== pointerId) return;
    lastX = event.clientX;
    lastY = event.clientY;
    const dx = event.clientX - startX;
    const dy = event.clientY - startY;
    if (!active) {
      if (Math.hypot(dx, dy) < threshold) return;
      beginDrag(event.clientX, event.clientY);
    }
    event.preventDefault();
    if (active) applyDragPosition(event.clientX, event.clientY);
    if (!active || !slotsReady) return;

    const overId = findSlotAt(event.clientX, event.clientY);
    dragOverId.value = overId;
    const fromIndex = findIndexById(draggingId.value);
    const overIndex = findIndexById(overId);
    if (!overId || fromIndex < 0 || overIndex < 0 || fromIndex === overIndex) return;

    slotsReady = false;
    const before = captureVisualRects();
    moveItem(fromIndex, overIndex);
    playFlip(before);
  }

  function handlePointerUp(event: PointerEvent) {
    if (pointerId != null && event.pointerId !== pointerId) return;
    teardown();
    pointerId = null;
    startIndex = -1;
    const wasActive = active;
    active = false;
    if (!wasActive) {
      draggingId.value = null;
      dragOverId.value = null;
      return;
    }
    if (slotsReady) settleDraggedItem();
    if (suppressClick) {
      window.setTimeout(() => {
        suppressClick = false;
      }, 0);
    }
  }

  function onPointerDown(event: PointerEvent, index: number) {
    if (event.button !== 0) return;
    if (shouldIgnore(event.target)) return;
    if (index < 0 || index >= items.value.length) return;
    pointerId = event.pointerId;
    startIndex = index;
    startX = event.clientX;
    startY = event.clientY;
    lastX = event.clientX;
    lastY = event.clientY;
    active = false;
    window.addEventListener("pointermove", handlePointerMove, { passive: false });
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
  }

  function consumeSuppressedClick() {
    if (!suppressClick) return false;
    suppressClick = false;
    return true;
  }

  onBeforeUnmount(() => {
    teardown();
    settleToken += 1;
    flipToken += 1;
    itemElements().forEach(clearMotion);
    draggingId.value = null;
    dragOverId.value = null;
    active = false;
    suppressClick = false;
  });

  return {
    draggingId,
    dragOverId,
    isSorting,
    onPointerDown,
    consumeSuppressedClick,
  };
}
