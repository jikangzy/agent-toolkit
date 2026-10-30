/** No synthesis, dependency installation, or temporary speech in the silent preview. */
window.MingAudioProvider = Object.freeze({
  status: 'silent_visual_preview', timing: 'provisional',
  async loadVerifiedWav(manifest) {
    if (!manifest || manifest.status !== 'pronunciation_reviewed' || !manifest.sha256 || !manifest.duration || !manifest.src.endsWith('.wav')) throw new Error('Reviewed WAV manifest required');
    return Object.freeze({...manifest});
  }
});
