// Signed document links open in a new tab. The tab opens on the click itself,
// before the request, so phone browsers don't block it as a popup.
export async function openSigned(load: () => Promise<{ url: string }>): Promise<void> {
  const tab = window.open('', '_blank')
  if (tab) tab.opener = null
  try {
    const { url } = await load()
    if (tab) tab.location.href = url
    else window.location.assign(url)
  } catch (error) {
    tab?.close()
    throw error
  }
}
