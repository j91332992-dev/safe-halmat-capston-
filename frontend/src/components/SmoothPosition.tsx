import {useLayoutEffect, useRef, type SVGProps} from "react";

type Props = Omit<SVGProps<SVGGElement>, "transform"> & {x: number; y: number; resetKey: string};

// Presentation only: interpolate to received coordinates, never extrapolate.
export function SmoothPosition({x, y, resetKey, children, ...props}: Props) {
  const node = useRef<SVGGElement>(null);
  const current = useRef({x, y, resetKey});
  useLayoutEffect(() => {
    let frame = 0;
    const from = {...current.current};
    const snap = from.resetKey !== resetKey || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const started = performance.now();
    const draw = (now: number) => {
      const fraction = snap ? 1 : Math.min(1, (now-started)/100);
      const px = from.x+(x-from.x)*fraction, py = from.y+(y-from.y)*fraction;
      current.current = {x:px, y:py, resetKey};
      node.current?.setAttribute("transform", `translate(${px},${py})`);
      if (fraction < 1) frame = requestAnimationFrame(draw);
    };
    draw(started);
    return () => cancelAnimationFrame(frame);
  }, [x, y, resetKey]);
  return <g {...props} ref={node} transform={`translate(${current.current.x},${current.current.y})`}>{children}</g>;
}
