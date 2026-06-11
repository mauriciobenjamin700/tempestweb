// native/audio.js — browser HTMLAudioElement glue for the N1 audio capability.
//
// One Audio element per channel; a new sound on a channel replaces the previous.
// Browsers block autoplay until the first user gesture — a blocked play resolves
// `{ played:false, blocked:true }` instead of throwing (graceful degradation).

import { CapabilityError } from "./index.js";

/** @type {Map<string, HTMLAudioElement>} per-channel players. */
const players = new Map();

/**
 * Play a short sound on a channel.
 * @param {{src:string,volume:number,channel:string}} args
 * @param {import("./index.js").NativeDeps} deps
 * @returns {Promise<{played:boolean,blocked:boolean,channel:string}>}
 */
export async function audioPlay(args, deps) {
  const channel = args.channel || "default";
  const AudioCtor = deps.Audio || /** @type {any} */ (globalThis).Audio;
  if (!AudioCtor) throw new CapabilityError("unavailable", "Audio is not available");

  const previous = players.get(channel);
  if (previous) {
    previous.pause();
  }
  const el = new AudioCtor(args.src);
  el.volume = typeof args.volume === "number" ? args.volume : 1.0;
  players.set(channel, el);

  try {
    const maybe = el.play();
    if (maybe && typeof maybe.then === "function") await maybe;
    return { played: true, blocked: false, channel };
  } catch {
    // NotAllowedError (autoplay blocked) is normal before a user gesture.
    return { played: false, blocked: true, channel };
  }
}

/**
 * Stop and reset playback on a channel.
 * @param {{channel:string}} args
 * @returns {Promise<Object>}
 */
export async function audioStop(args) {
  const channel = args.channel || "default";
  const el = players.get(channel);
  if (el) {
    el.pause();
    try {
      el.currentTime = 0;
    } catch {
      // jsdom Audio may not implement currentTime; ignore.
    }
  }
  return {};
}
