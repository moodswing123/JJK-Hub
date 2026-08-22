# 🌀 Jujutsu Kaisen Telegram Game Bot   
RPG bot
<h3>
<em>fun roleplaying game that takes you into the world of jujutsu kaisen in real time - hop on the game and enjoy </em> 
</h3>
<br>

<p>to reach me contact - <a href="https://wa.me/2347038253086">whatsapp </a> </p>

<h1> MY AIMS FOR THE GAME</h1>
<p> <strong> i hope to create a RPG game where anime fans from all over the world can come and share their experiences and have fun </strong> </p>

<table border="1">
<tr>
  <th> <strong> GAME FEATURES </strong> </th>
  <th> <strong> DEVELOPER </strong> </th>
  <th> <strong> COMMANDS </strong> </th>
</tr>
  <td> jujutsu kaisen </td>
    <td> Victory </td>
    <td> start </td>
  
<tr>
  <td> domains </td>
  <td> horlapookie ˢʸᴺˣ </td>
 <td> inventory (etx) </td>
</tr>
<tr>
  <td> economy system </td>
  <td> null </td>
  <td> challenge </td>
</tr>

</table>

## Gemini-powered `/debug`

The owner-only `/debug` command runs deterministic database, player, battle, and integrity checks first. If `GEMINI_API_KEY` is configured in the bot deployment, it then sends a redacted, bounded diagnostic report to Gemini for a concise root-cause review. The AI review is advisory only; it cannot execute code, change the database, or repair production state. If the key is missing or Gemini times out, deterministic diagnostics still complete normally. Configure `GEMINI_API_KEY` as a deployment secret and optionally set `GEMINI_MODEL` (default: `gemini-3.6-flash`).

## Battle media provider note

The bot currently uses its Pillow-based generated GIF pipeline for `/battle`, `/ch`, and bot challenges. A connector inspection found no enabled Nano Banana provider or compatible free credential in the deployment configuration, so Nano Banana cannot be activated safely at this time. The Pillow pipeline is therefore the supported implementation; replacing it later requires a supported image-generation API and deployment secret.
