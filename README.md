# splitRP
**-Speedrunning Autosplitter for use with LiveSplit**
*(supporting both RTA and IGT timing)*

## Rebuild
This branch is a complete rebuild of SplitRP from the ground up.

	- Split-detection has been changed to a difference-map method, using OpenCV's native methods
	  to compare stored images against what's on screen.
	
	- Run states have been simplified to:
		> Match Cycle (seeking a match)
			: Match found - Begin Unmatch cycle.
		> Unmatch Cycle (if lost current match)
			: Matched the unmatch test specified - Begin match cycle seeking unmatch test.
			: No match - Begin match cycle seeking nomatch test.
			
	- Comparison employs two values. The percentage similarity needed to make a match, and the percentage needed
	  to break out of a match.

