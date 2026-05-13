# Reads the UserPromptSubmit hook JSON from stdin.
# If file attachments are detected, injects additionalContext that instructs Claude to:
#   1. Run all applicable skills sequentially (no user prompting)
#   2. Write all skill outputs to a timestamped txt file in the working directory.

$raw = [Console]::In.ReadToEnd()
if (-not $raw) { exit 0 }

try {
    $jsonStr = $raw

    # Detect file attachments by looking for:
    #   - image/document/file content-type blocks
    #   - common file extensions referenced in the payload
    #   - base64 blobs (large data strings indicating binary uploads)
    $hasFiles = ($jsonStr -match '"type"\s*:\s*"(image|document|file|attachment)"') -or
                ($jsonStr -match '\.(pdf|txt|csv|json|py|js|ts|md|xml|xlsx|docx|png|jpg|jpeg|gif|zip)"') -or
                ($jsonStr -match '"data"\s*:\s*"[A-Za-z0-9+/]{200,}={0,2}"')

    if ($hasFiles) {
        $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
        $outputFile = "skill_output_$ts.txt"
        $ctx = @"
FILES DETECTED: The user has uploaded one or more files with this message.
You MUST follow these steps WITHOUT waiting for the user to trigger each one:
1. Inspect the uploaded files and determine ALL skills that apply to them.
2. Run each applicable skill sequentially using the Skill tool (one at a time).
3. Capture the output/result of each skill as you go.
4. After ALL skills have completed, write every skill's name and its full output to a file named "$outputFile" in the current working directory using the Write tool.
5. Inform the user that "$outputFile" is ready in the project directory.
Do NOT skip any of these steps or wait for user confirmation between skills.
"@
        $result = [ordered]@{
            hookSpecificOutput = [ordered]@{
                hookEventName   = "UserPromptSubmit"
                additionalContext = $ctx
            }
        }
        $result | ConvertTo-Json -Depth 5
    }
} catch {
    # Silent failure — never block the user's message
}
