// counter.gen.js — GENERATED from examples/counter/app.py (Mode C transpile).

import { State } from "./runtime.js";
import { Button, Column, Edge, Row, Style, Text } from "./widgets.js";

export class CounterState extends State {
  constructor() {
    super();
    this.value = 0;
  }
}

export function makeState() {
  return new CounterState();
}

export function view(app) {
  const increment = () => {
    app.setState((s) => {
      s.value = (s.value + 1);
    });
  };
  const decrement = () => {
    app.setState((s) => {
      s.value = (s.value - 1);
    });
  };
  return Column({
    style: Style({ gap: 8.0, padding: Edge.all(16) }),
    children: [
      Text({ content: `Count: ${app.state.value}`, key: "label" }),
      Row({
        style: Style({ gap: 4.0 }),
        children: [
          Button({ label: "-", onClick: decrement, key: "dec" }),
          Button({ label: "+", onClick: increment, key: "inc" }),
        ],
      }),
    ],
  });
}
